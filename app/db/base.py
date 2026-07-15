# app/db/base.py
from sqlalchemy.orm import declarative_base

# Shares metadata mapping definitions across all individual model files
Base = declarative_base()