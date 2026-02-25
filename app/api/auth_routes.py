from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserOut
from app.services.auth_service import (
    create_access_token,
    get_current_user,
    get_user_by_email,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(body: UserCreate, session: Session = Depends(get_session)):
    existing = get_user_by_email(session, body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, session: Session = Depends(get_session)):
    user = get_user_by_email(session, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut(id=current_user.id, email=current_user.email, full_name=current_user.full_name)

