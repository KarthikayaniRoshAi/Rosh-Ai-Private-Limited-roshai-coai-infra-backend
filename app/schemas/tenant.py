# app/schemas/tenant.py
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import List
import re

class CustomerCreatePayload(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=100, example="Acme Corp")
    admin_emailid: EmailStr = Field(..., example="admin@acme.com")  # Enforces valid email formats automatically
    region: str = Field(..., example="chennai")
    environment_name: str = Field(..., example="Production")
    customer_code: str = Field(..., example="acme")
    domain_subdomain: str = Field(..., example="acme.yourdomain.com")
    aws_region: str = Field(..., example="ap-south-1")
    cloud_provider: str = Field(..., example="aws")
    iqi_apps_requested: List[str] = Field(..., min_items=1, example=["iqi-frontend"])
    plan_type: str = Field(..., example="Standard Cluster Tier")
    engineer_actor: str = Field(..., example="engineer_john")

    @field_validator('customer_code')
    @classmethod
    def validate_customer_code(cls, value: str) -> str:
        # Enforce clean alphanumeric slug patterns (no spaces, special chars, uppercase characters)
        if not re.match(r"^[a-z0-9-_]+$", value):
            raise ValueError("customer_code must be lower-case alphanumeric, dashes, or underscores only.")
        return value
    
    
