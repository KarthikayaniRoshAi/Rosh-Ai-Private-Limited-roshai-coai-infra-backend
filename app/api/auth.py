# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
# from app.models.user import User 
from app.services.auth import verify_password, create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/login", status_code=status.HTTP_200_OK)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    Standard OAuth2 compatible token login endpoint.
    Expects standard body form data fields: 'username' and 'password'.
    """
    # 1. Fetch user by username/email from your database table
    # user = db.query(User).filter(User.email == form_data.username).first()
    
    if form_data.username != "akshu@email.com" or form_data.password != "akshu123":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 2. Once validated, issue the cryptographically signed JWT token back to the UI
    access_token = create_access_token(data={"sub": form_data.username, "role": "Engineer"})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": form_data.username,
            "role": "Engineer"
        }
    }