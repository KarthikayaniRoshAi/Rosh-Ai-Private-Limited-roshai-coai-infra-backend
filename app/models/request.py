from sqlalchemy import Column, String
from app.db.base import Base

class DeploymentRequest(Base):
    __tablename__ = "DEPLOYMENT_REQUESTS"
    id = Column(String(36), primary_key=True)
    customer_id = Column(String(36), nullable=False)
    environment_id = Column(String(36), nullable=False)
    scenario = Column(String(50))
    status = Column(String(50))
    customer_code = Column(String(50))
    domain_subdomain = Column(String(255))
    aws_region = Column(String(100))

class CloudTarget(Base):
    __tablename__ = "CLOUD_TARGETS"
    id = Column(String(36), primary_key=True)
    deployment_request_id = Column(String(36), nullable=False)
    provider = Column(String(50))
    region = Column(String(100))

class VMTarget(Base):
    __tablename__ = "VM_TARGETS"
    id = Column(String(36), primary_key=True)
    deployment_request_id = Column(String(36), nullable=False)
    host = Column(String(255))