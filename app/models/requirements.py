from sqlalchemy import Column, String, JSON
from app.db.base import Base

class CoaiRequirement(Base):
    __tablename__ = "COAI_REQUIREMENTS"
    id = Column(String(36), primary_key=True)
    deployment_request_id = Column(String(36), nullable=False)
    iqi_apps_requested = Column(JSON, nullable=False) # Saves your array list