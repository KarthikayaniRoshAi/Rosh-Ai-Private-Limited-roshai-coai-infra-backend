# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Local MySQL connection URL configuration
# Format: mysql+pymysql://<user>:<password>@<host>:<port>/<database_name>
DATABASE_URL = "mysql+pymysql://root:root123@localhost:3306/deployment_orchestrator_db"

# Create the core SQLAlchemy connection engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Automatically checks if connection is alive before executing
    pool_size=5,         # Standard local pool allocation limit
    max_overflow=10
)

# Session factory configuration
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency wrapper injected into your FastAPI route controllers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()