from __future__ import annotations

from sqlmodel import SQLModel
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.roles import ROLE_ADMIN
from app.db.engine import get_engine
from app.db.migrate import ensure_instruments_is_etf_column, ensure_users_role_column
from app.models.user import User
from app.services.auth_service import hash_password, verify_password


def ensure_seed_admin(engine) -> None:
    """Ensure a deterministic default admin account exists for admin panel login."""
    settings = get_settings()
    legacy_seed_email = "admin@stockgo.local"
    with Session(engine) as session:
        admin_user = session.exec(select(User).where(User.email == settings.admin_seed_email)).first()
        if admin_user is None and settings.admin_seed_email != legacy_seed_email:
            legacy_user = session.exec(select(User).where(User.email == legacy_seed_email)).first()
            if legacy_user is not None:
                legacy_user.email = settings.admin_seed_email
                admin_user = legacy_user

        if admin_user is None:
            admin_user = User(
                email=settings.admin_seed_email,
                full_name=settings.admin_seed_username,
                hashed_password=hash_password(settings.admin_seed_password),
                role=ROLE_ADMIN,
            )
            session.add(admin_user)
            session.commit()
            return

        changed = False
        # Keep seeded account deterministic so admin/admin panel login always works.
        if admin_user.full_name != settings.admin_seed_username:
            admin_user.full_name = settings.admin_seed_username
            changed = True
        if admin_user.role != ROLE_ADMIN:
            admin_user.role = ROLE_ADMIN
            changed = True
        password_ok = False
        if admin_user.hashed_password:
            try:
                password_ok = verify_password(settings.admin_seed_password, admin_user.hashed_password)
            except Exception:
                password_ok = False
        if not password_ok:
            admin_user.hashed_password = hash_password(settings.admin_seed_password)
            changed = True

        if changed:
            session.add(admin_user)
            session.commit()


def init_db() -> None:
    # Ensure models are imported so metadata is populated
    import app.models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    ensure_instruments_is_etf_column(engine)
    ensure_users_role_column(engine)
    ensure_seed_admin(engine)

