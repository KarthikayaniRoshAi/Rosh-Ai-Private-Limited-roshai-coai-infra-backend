from sqlalchemy import Column, String, Integer, BigInteger
from app.db.base import Base

class DeploymentRun(Base):
    __tablename__ = "DEPLOYMENT_RUNS"
    id = Column(String(36), primary_key=True)
    deployment_request_id = Column(String(36), nullable=False)
    plan_id = Column(String(36), nullable=False)
    status = Column(String(50))
    progress_percentage = Column(Integer, default=0)

class HealthCheck(Base):
    __tablename__ = "HEALTH_CHECKS"
    id = Column(String(36), primary_key=True)
    deployment_run_id = Column(String(36), nullable=False)
    check_type = Column(String(100))
    status = Column(String(100))

class AuditLog(Base):
    __tablename__ = "AUDIT_LOG"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    deployment_request_id = Column(String(36), nullable=False)
    actor = Column(String(100), nullable=False)
    action = Column(String(255), nullable=False)