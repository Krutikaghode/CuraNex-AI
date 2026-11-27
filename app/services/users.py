from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.models import User


class DuplicateUserError(ValueError):
    pass


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def create_user(db: Session, *, email: str, full_name: str, password: str, role: str) -> User:
    user = User(
        email=email.strip().lower(),
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise DuplicateUserError("A user with this email already exists.") from error
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if not verify_password(password, user.password_hash if user else None):
        return None
    if not user.is_active:
        return None
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def count_users(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User)) or 0)


def set_active(db: Session, user_id: int, active: bool) -> User | None:
    user = db.get(User, user_id)
    if user is None:
        return None
    user.is_active = active
    db.commit()
    db.refresh(user)
    return user
