"""Admin API: login + user role management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.roles import ALL_ROLES, ROLE_ADMIN, is_valid_role
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import AdminLoginRequest, AdminUserOut, AdminUserUpdate, TokenResponse, UserOut
from app.services.auth_service import create_access_token, get_current_admin, verify_password

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_to_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=getattr(user, "role", "member"),
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.post("/login", response_model=TokenResponse)
def admin_login(body: AdminLoginRequest, session: Session = Depends(get_session)):
    """Username/password login dedicated to admin panel."""
    settings = get_settings()
    if body.username.strip() != settings.admin_seed_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = session.exec(select(User).where(User.email == settings.admin_seed_email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")

    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role),
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
):
    """List all users (admin only)."""
    users = session.exec(select(User).order_by(User.id)).all()
    return [_user_to_out(u) for u in users]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user_role(
    user_id: int,
    body: AdminUserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin),
):
    """Update a user's role (admin only)."""
    if not is_valid_role(body.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {ALL_ROLES}",
        )

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = body.role
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_to_out(user)


@router.get("/roles")
def get_roles(current_user: User = Depends(get_current_admin)):
    """Return role keys and English labels for admin UI."""
    role_labels = {
        "member": "Member",
        "intermediate": "Intermediate",
        "advanced": "Advanced",
        "admin": "Admin",
    }
    return {"roles": [{"key": role, "label": role_labels.get(role, role)} for role in ALL_ROLES]}


@router.get("", response_class=HTMLResponse)
def admin_page():
    """Simple backend placeholder page. Main admin UI lives in Next.js (/admin)."""
    return HTMLResponse(
        """
        <!doctype html>
        <html lang=\"en\">
          <head>
            <meta charset=\"utf-8\" />
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
            <title>StockGo Admin API</title>
          </head>
          <body style=\"font-family: system-ui, -apple-system, sans-serif; padding: 24px;\">
            <h1>StockGo Admin API</h1>
            <p>The admin UI is available on the frontend at <a href=\"http://127.0.0.1:3000/admin\">/admin</a>.</p>
          </body>
        </html>
        """
    )


@router.get("/", response_class=HTMLResponse)
def admin_page_slash():
    return admin_page()
