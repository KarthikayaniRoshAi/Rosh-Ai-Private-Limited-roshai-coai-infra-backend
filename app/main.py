import os
import sys

# Force the project root directory into Python's module search path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import tenants
from app.api.auth import router as auth_router  
from app.db.session import engine
from app.models import Base


app = FastAPI(
    title="COAI Infrastructure Provisioning Engine Backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)  
app.include_router(tenants.router)

# Creates all tables in your local MySQL database if they don't exist yet
Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"status": "online", "message": "Control Plane API operational Gateway"}