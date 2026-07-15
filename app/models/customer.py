from sqlalchemy import Column, String
from app.db.base import Base

class Customer(Base):
    __tablename__ = "CUSTOMERS"
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    admin_emailid = Column(String(100))
    region = Column(String(100))

class Environment(Base):
    __tablename__ = "ENVIRONMENTS"
    id = Column(String(36), primary_key=True)
    customer_id = Column(String(36), nullable=False)
    name = Column(String(100), nullable=False)