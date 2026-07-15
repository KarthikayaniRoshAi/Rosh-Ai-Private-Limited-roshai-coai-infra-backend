# app/api/tenants.py
import uuid
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.tenant import CustomerCreatePayload
from app.models.customer import Customer, Environment
from app.models.request import DeploymentRequest, CloudTarget
from app.models.requirements import CoaiRequirement
from app.models.governance import Plan, Approval
from app.models.engine_audit import DeploymentRun, AuditLog

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
        with db.begin():
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

            # ─── UPDATING THE APPROVAL TABLE ONLY ON SUCCESSFUL 'PASS' ───
            new_approval = Approval(
                id=str(uuid.uuid4()),
                deployment_request_id=new_request.id,
                plan_id=new_plan.id,
                decision="PASS" # Updated status to "PASS" as requested!
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failure: {str(e)}"
        )