from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
import re
import uuid
from datetime import datetime, timedelta

from app.db.database import (
    create_user,
    get_user_by_email,
    update_user_reset_token,
    get_user_by_reset_token,
    update_user_password
)
from app.utils.hash_utils import hash_password, verify_password
from app.utils.jwt_utils import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Regex for basic email validation (since we don't assume EmailStr packages exist/are working if we want to be safe, but Pydantic EmailStr can be used, though a regex is extremely bulletproof and self-contained).
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    password: str

@router.post("/register")
def register(req: RegisterRequest):
    # Validate name
    name_clean = req.name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
        
    # Validate email
    email_clean = req.email.strip().lower()
    if not re.match(EMAIL_REGEX, email_clean):
        raise HTTPException(status_code=400, detail="Invalid email address format")
        
    # Validate password
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
    # Check if user already exists
    existing_user = get_user_by_email(email_clean)
    if existing_user:
        raise HTTPException(status_code=400, detail="A user with this email address already exists")
        
    # Hash password & create user
    hashed = hash_password(req.password)
    user = create_user(name_clean, email_clean, hashed)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user account")
        
    # Generate JWT token
    token = create_access_token({"id": user["id"], "name": user["name"], "email": user["email"]})
    
    return {
        "message": "User registered successfully",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    }

@router.post("/login")
def login(req: LoginRequest):
    email_clean = req.email.strip().lower()
    user = get_user_by_email(email_clean)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    # Generate token
    token = create_access_token({"id": user["id"], "name": user["name"], "email": user["email"]})
    
    return {
        "message": "Logged in successfully",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    }

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    email_clean = req.email.strip().lower()
    user = get_user_by_email(email_clean)
    
    if not user:
        # Avoid user enumeration by returning a success message anyway
        return {"message": "If that email is registered, a reset link has been generated."}
        
    # Generate reset token (valid for 1 hour)
    token = str(uuid.uuid4())
    expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    
    update_user_reset_token(email_clean, token, expires)
    
    reset_url = f"http://localhost:5173/reset-password?token={token}"
    
    print("\n" + "="*50)
    print(f"PASSWORD RESET REQUEST FOR: {email_clean}")
    print(f"Reset Token: {token}")
    print(f"Reset URL: {reset_url}")
    print("="*50 + "\n")
    
    return {
        "message": "Reset token generated successfully.",
        "token": token,  # Returned for ease of development/testing
        "reset_url": reset_url
    }

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
    user = get_user_by_reset_token(req.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
    # Check expiration
    expires_str = user["reset_token_expires"]
    if expires_str:
        expires = datetime.fromisoformat(expires_str)
        if expires < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Reset token has expired")
            
    # Update password and clear reset token fields
    hashed = hash_password(req.password)
    update_user_password(user["id"], hashed)
    
    return {"message": "Password reset successfully. You can now login with your new password."}
