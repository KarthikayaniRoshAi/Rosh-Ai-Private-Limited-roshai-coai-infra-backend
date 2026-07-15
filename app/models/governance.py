from sqlalchemy import Column, String, Boolean
from app.db.base import Base

class Plan(Base):
    __tablename__ = "PLANS"
    id = Column(String(36), primary_key=True)
    deployment_request_id = Column(String(36), nullable=False)
    plan_type = Column(String(100))
    has_destructive_changes = Column(Boolean, default=False)

class Approval(Base):
    __tablename__ = "APPROVALS"
    id = Column(String(36), primary_key=True)
    deployment_request_id = Column(String(36), nullable=False)
    plan_id = Column(String(36), nullable=False)
    decision = Column(String(50))