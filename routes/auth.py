"""
Auth Route — Registration, login, and profile management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from models.database import get_db, User
from models.schemas import RegisterRequest, LoginRequest, AuthResponse, UserResponse
from services.auth_utils import (
    hash_password, verify_password, create_access_token,
    generate_api_key, get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user. First user in an org becomes admin."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # First user in org = admin
    org_user_count = db.query(User).filter(
        User.organisation == payload.organisation
    ).count() if payload.organisation else 0
    role = "admin" if org_user_count == 0 else "viewer"

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        organisation=payload.organisation,
        department=payload.department,
        role=role,
        api_key=generate_api_key(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role)
    return AuthResponse(access_token=token, user=user)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token(user.id, user.role)
    return AuthResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/generate-key")
async def generate_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rotate API key for the current user."""
    current_user.api_key = generate_api_key()
    db.commit()
    return {
        "api_key": current_user.api_key,
        "message": "New API key generated. Previous key is now invalid.",
        "warning": "Store this key securely — it will not be shown again.",
    }
