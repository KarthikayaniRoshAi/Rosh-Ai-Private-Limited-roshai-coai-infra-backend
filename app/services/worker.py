# app/services/worker.py
import subprocess
import os
import time
import logging
from sqlalchemy.orm import Session
from app.models.engine_audit import AuditLog, DeploymentRun
from app.models.governance import Approval

logger = logging.getLogger("uvicorn.error")

# TOGGLE FLAG: Set to True to test the UI polling framework without real scripts.
# Set to False once the infra team delivers the folder tree to point to the real binary engine.
MOCK_TERRAFORM = True

def run_terraform_pipeline(request_id: str, payload_dict: dict, db_factory):
    """
    Background worker that handles the infrastructure provisioning stage.
    Streams execution logs line-by-line straight to the AUDIT_LOG table
    so the frontend dashboard 10-second polling loop can catch them.
    """
    # Open an independent database session for the worker background thread context
    db: Session = db_factory()
    
    # Establish absolute directory path to where the infra team's script execution root lives
    tf_dir = os.path.abspath("./infra/terraform/projects/dmt/dev")
    
    # Map incoming validation parameters cleanly into CLI terminal override argument strings
    tf_vars = [
        "-var", f"customer_name={payload_dict.get('customer_name', '')}",
        "-var", f"customer_code={payload_dict.get('customer_code', '')}",
        "-var", f"aws_region={payload_dict.get('aws_region', '')}",
        "-var", f"cloud_provider={payload_dict.get('cloud_provider', '')}"
    ]
    
    logger.info(f"Starting infrastructure provisioning loop for Request ID: {request_id}")

    try:
        # ─── CASE A: RUNNING IN MOCK SIMULATION MODE ───
        if MOCK_TERRAFORM:
            logger.info("MOCK_TERRAFORM is enabled. Simulating infrastructure build milestones...")
            
            # Step 1: Mock initialization phase
            db.add(AuditLog(
                deployment_request_id=request_id,
                actor="System",
                action="[MOCK] Initializing remote state connection backends and provider plugins..."
            ))
            db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"progress_percentage": 10})
            db.commit()
            time.sleep(2)

            # Step 2: Stream simulated log lines mimicking typical cloud workspace outputs
            mock_milestones = [
                (25, "Terraform Engine", "[MOCK] Plan: 14 resources to add, 0 to change, 0 to destroy."),
                (45, "Terraform Engine", "[MOCK] aws_vpc.custom_tenant_vpc: Creating... [id=pending]"),
                (60, "Terraform Engine", "[MOCK] aws_internet_gateway.gw: Creating network boundaries..."),
                (75, "Terraform Engine", "[MOCK] aws_security_group.app_sg: Applying security ingress groups..."),
                (90, "Terraform Engine", "[MOCK] aws_instance.main_app_host: Provisioning EC2 virtual machine node cluster...")
            ]

            for progress, actor, action in mock_milestones:
                db.add(AuditLog(deployment_request_id=request_id, actor=actor, action=action))
                db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"progress_percentage": progress})
                db.commit()
                time.sleep(2) # Pauses briefly so you can actually watch it happen on your UI dashboard panels

            # ─── STEP 3: MOCK PROVISIONING FINISHED & URL CAPTURED ───
            generated_mock_url = f"https://{payload_dict.get('customer_code', 'tenant')}.coai-platform.net"
            db.add(AuditLog(
                deployment_request_id=request_id, 
                actor="System", 
                action=f"[MOCK] Infrastructure created successfully. Endpoint generated: {generated_mock_url}"
            ))
            db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"progress_percentage": 75})
            db.commit()
            time.sleep(2)

            # ─── STEP 4: MOCK QA SMOKE TESTING HANDOFF ───
            db.add(AuditLog(
                deployment_request_id=request_id, 
                actor="QA Test Engine", 
                action=f"[MOCK] Invoking smoke test scripts wrapper against target: {generated_mock_url}"
            ))
            db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"progress_percentage": 85})
            db.commit()
            time.sleep(2)

            db.add(AuditLog(
                deployment_request_id=request_id, 
                actor="QA Test Engine", 
                action="✔ [MOCK] All 12 primary application smoke test assertions PASSED successfully."
            ))
            db.commit()

            # ─── STEP 5: MOCK ENGINE HEALTH CHECK ENGINE ───
            db.add(AuditLog(
                deployment_request_id=request_id, 
                actor="System Health Monitor", 
                action="[MOCK] Initiating application baseline heartbeat polling sequence on pathway /health..."
            ))
            db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"progress_percentage": 95})
            db.commit()
            time.sleep(2)

            # ─── STEP 6: PIPELINE COMPLETE ───
            db.query(Approval).filter(Approval.deployment_request_id == request_id).update({"decision": "PROVISIONING_SUCCESS"})
            db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"status": "SUCCESS", "progress_percentage": 100})
            db.add(AuditLog(
                deployment_request_id=request_id, 
                actor="System", 
                action="[MOCK] Tenant workspace initialization complete. Environment state flipped to ACTIVE."
            ))
            db.commit()
            
        # ─── CASE B: RUNNING THE REAL BINARY PIPELINE ENGINE ───
        else:
            logger.info(f"Invoking active shell subprocess execution inside target workspace: {tf_dir}")
            
            # 1. Run 'terraform init'
            init_process = subprocess.run(
                ["terraform", "init", "-no-color"],
                cwd=tf_dir, capture_output=True, text=True, check=True
            )
            db.add(AuditLog(deployment_request_id=request_id, actor="System", action="Terraform modules initialized successfully."))
            db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"progress_percentage": 15})
            db.commit()

            # 2. Run 'terraform apply' non-blocking stream loop
            cmd = ["terraform", "apply", "-auto-approve", "-no-color"] + tf_vars
            process = subprocess.Popen(
                cmd, cwd=tf_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )

            # 3. Actively read the terminal stdout stream as lines are printed by the binary process
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line.strip():
                    cleaned_line = line.strip()
                    db.add(AuditLog(deployment_request_id=request_id, actor="Terraform Engine", action=cleaned_line))
                    
                    # Dynamically increment the percentage metric based on text matches to make loading organic
                    if "Creating..." in cleaned_line:
                        db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"progress_percentage": 50})
                    elif "Modifying..." in cleaned_line:
                        db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"progress_percentage": 70})
                        
                    db.commit()

            # 4. Process Close Verification Assessment
            if process.returncode == 0:
                # Once real infra finishes, this placeholder can be replaced with real QA script runs
                db.query(Approval).filter(Approval.deployment_request_id == request_id).update({"decision": "PROVISIONING_SUCCESS"})
                db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"status": "SUCCESS", "progress_percentage": 100})
                db.add(AuditLog(deployment_request_id=request_id, actor="System", action="Infrastructure pipeline successfully completed."))
                db.commit()
            else:
                raise subprocess.CalledProcessError(process.returncode, cmd)

    except Exception as err:
        logger.error(f"Execution engine failure on pipeline ID {request_id}: {str(err)}")
        db.rollback()
        db.query(Approval).filter(Approval.deployment_request_id == request_id).update({"decision": "PROVISIONING_FAILED"})
        db.query(DeploymentRun).filter(DeploymentRun.deployment_request_id == request_id).update({"status": "FAILED"})
        db.add(AuditLog(
            deployment_request_id=request_id, 
            actor="System", 
            action=f"Orchestration worker crash loop error: {str(err)}"
        ))
        db.commit()
        
    finally:
        db.close()
        logger.info(f"Worker run loop wrapped up for request reference context: {request_id}")