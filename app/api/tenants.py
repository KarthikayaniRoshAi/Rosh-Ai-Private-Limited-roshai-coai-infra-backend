# app/api/tenants.py
import uuid
import re
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, get_db
from app.schemas.tenant import CustomerCreatePayload
from app.models.customer import Customer, Environment
from app.models.request import DeploymentRequest, CloudTarget
from app.models.requirements import CoaiRequirement
from app.models.governance import Plan, Approval
from app.models.engine_audit import DeploymentRun, AuditLog
from app.services.worker import run_terraform_pipeline

router = APIRouter(prefix="/api/v1/customers", tags=["Customer Management"])

# Setup a clean validation helper map for dynamic cloud configurations
ALLOWED_CLOUD_REGIONS = {
    "aws": ["ap-south-1", "us-east-1", "eu-west-1"],
    "azure": ["centralindia", "eastus", "westeurope"],
    "gcp": ["asia-south1", "us-central1", "europe-west1"]
}

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_new_customer(payload: CustomerCreatePayload, db: Session = Depends(get_db)):
    
    # ─── GATING LAYER 1: UNIQUE IDENTIFIER CONFLICT CHECK ───
    existing_slug = db.query(Customer).filter(Customer.slug == payload.customer_code).first()
    if existing_slug:
        # If this fails, code execution stops here. The UI catches this exact error message.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation Failed: The customer code '{payload.customer_code}' is already taken."
        )

    # ─── GATING LAYER 2: PROVIDER CHECK ───
    provider = payload.cloud_provider.lower()
    if provider not in ALLOWED_CLOUD_REGIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation Failed: Unsupported cloud provider '{payload.cloud_provider}'."
        )
        
    # ─── GATING LAYER 3: REGION COMPATIBILITY MATRIX CHECK ───
    valid_regions = ALLOWED_CLOUD_REGIONS[provider]
    if payload.aws_region not in valid_regions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation Failed: {provider.upper()} does not support zone '{payload.aws_region}'."
        )

   # ─── IF ALL VALIDATIONS ABOVE PASSED, THE CODE CONTINUES HERE ───
    try:
        # 1. Populate Core Customer Profile
        new_customer = Customer(
            id=str(uuid.uuid4()),
            name=payload.customer_name,
            slug=payload.customer_code,
            admin_emailid=payload.admin_emailid,
            region=payload.region
        )
        db.add(new_customer)

        new_env = Environment(
            id=str(uuid.uuid4()),
            customer_id=new_customer.id,
            name=payload.environment_name
        )
        db.add(new_env)

        # 2. Setup Deployment Request Configuration Tracker
        new_request = DeploymentRequest(
            id=str(uuid.uuid4()),
            customer_id=new_customer.id,
            environment_id=new_env.id,
            scenario="CLOUD",
            status="PROCESSING", 
            customer_code=payload.customer_code,
            domain_subdomain=payload.domain_subdomain,
            aws_region=payload.aws_region
        )
        db.add(new_request)

        new_cloud_target = CloudTarget(
            id=str(uuid.uuid4()),
            deployment_request_id=new_request.id,
            provider=payload.cloud_provider,
            region=payload.aws_region
        )
        db.add(new_cloud_target)

        new_requirement = CoaiRequirement(
            id=str(uuid.uuid4()),
            deployment_request_id=new_request.id,
            iqi_apps_requested=payload.iqi_apps_requested
        )
        db.add(new_requirement)

        new_plan = Plan(
            id=str(uuid.uuid4()),
            deployment_request_id=new_request.id,
            plan_type=payload.plan_type,
            has_destructive_changes=False
        )
        db.add(new_plan)

        # 3. UPDATING THE APPROVAL TABLE ONLY ON SUCCESSFUL 'PASS'
        new_approval = Approval(
            id=str(uuid.uuid4()),
            deployment_request_id=new_request.id,
            plan_id=new_plan.id,
            decision="PASS"
        )
        db.add(new_approval)

        # 4. Initialize Execution Run Engine Metrics
        new_run = DeploymentRun(
            id=str(uuid.uuid4()),
            deployment_request_id=new_request.id,
            plan_id=new_plan.id,
            status="RUNNING_TERRAFORM",
            progress_percentage=0 
        )
        db.add(new_run)

        # 5. Insert Primary Initialization Step Log Trace
        new_audit = AuditLog(
            deployment_request_id=new_request.id,
            actor="System",
            action="METADATA_VALIDATION_PASS_AUTOMATIC_TERRAFORM_TRIGGERED"
        )
        db.add(new_audit)

        # Commit everything to the database atomically at once
        db.commit()

        return {
            "success": True,
            "message": "Validation passed successfully.",
            "data": {
                "customer_id": new_customer.id,
                "deployment_request_id": new_request.id,
                "validation_status": "PASS"
            }
        }

    except Exception as e:
        db.rollback() # Safely rolls back changes if a DB connection failure occurs
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failure: {str(e)}"
        )
    
@router.get("/", status_code=status.HTTP_200_OK)
def list_all_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Fetches a list of all recorded customer profiles from the database.
    Includes built-in pagination limits for UI dashboard scaling.
    """
    try:
        # 1. Query the CUSTOMERS table with offset and maximum bounds
        customers = db.query(Customer).offset(skip).limit(limit).all()
        
        # 2. Format the records into a clean JSON list layout
        customer_list = []
        for customer in customers:
            customer_list.append({
                "customer_id": customer.id,
                "customer_name": customer.name,
                "customer_code": customer.slug,
                "admin_emailid": customer.admin_emailid,
                "region": customer.region
            })
            
        return {
            "success": True,
            "count": len(customer_list),
            "data": customer_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve customer matrix rows: {str(e)}"
        )

@router.post("/{request_id}/provision", status_code=status.HTTP_202_ACCEPTED)
def proceed_to_infrastructure_provisioning(
    request_id: str, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """
    Triggered manually by the UI 'Proceed' button.
    Launches the background automation pipeline worker loop.
    """
    # 1. Verify the deployment request exists
    run_record = db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).first()
    if not run_record:
        raise HTTPException(status_code=404, detail="Deployment request workspace profile not found.")
        
    # 2. Update status indicator state so the frontend UI polling loader wakes up
    db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({
        "status": "PROVISIONING_INFRASTRUCTURE",
        "progress_percentage": 5
    })
    
    # 3. Pull customer parameters out of DB to build payload dict for background thread
    request_data = db.query(DeploymentRequest).filter(DeploymentRequest.id == request_id).first()
    payload_dict = {
        "customer_name": request_data.customer_code, # Use data present from the DB record
        "customer_code": request_data.customer_code,
        "aws_region": request_data.aws_region,
        "cloud_provider": "aws" # Dynamically pulled in real scenario
    }
    
    db.commit()

    # 4. Hand off execution path directly to the background worker loop thread
    background_tasks.add_task(
        run_terraform_pipeline, 
        request_id=request_id, 
        payload_dict=payload_dict, 
        db_factory=SessionLocal
    )

    return {"success": True, "message": "Infrastructure orchestration engine successfully initialized."}
# app/api/tenants.py

@router.get("/{request_id}/logs", status_code=status.HTTP_200_OK)
def get_realtime_deployment_logs(request_id: str, db: Session = Depends(get_db)):
    """
    UI Polling Target: Hitted every 10 seconds by the frontend.
    Returns the current execution percentage status alongside the latest log trace lines.
    """
    # 1. Fetch the live progress metrics from the DeploymentRun table
    run_metrics = db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).first()
    if not run_metrics:
        raise HTTPException(status_code=404, detail="Active execution workspace metrics not found.")

    # 2. Fetch all log lines emitted by the worker so far, ordered chronologically
    logs = db.query(AuditLog).filter(AuditLog.deployment_request_id == request_id).order_by(AuditLog.id.asc()).all()

    # 3. Structure the payload array for the UI console terminal component
    log_stream = []
    for entry in logs:
        log_stream.append({
            "timestamp": str(entry.id), # Or your created_at field if present
            "source": entry.actor,      # e.g., "Terraform Engine", "QA Test Engine"
            "message": entry.action
        })

    return {
        "success": True,
        "current_status": run_metrics.status, # e.g., "RUNNING_TERRAFORM", "SUCCESS"
        "progress_percentage": run_metrics.progress_percentage, # Integer value (0 to 100)
        "logs": log_stream
    }