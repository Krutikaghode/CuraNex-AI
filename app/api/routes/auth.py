"""Sign-in and user management."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.security import create_access_token
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import Token, UserCreate, UserOut, UserStatusUpdate
from app.services import users as service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> dict:
    """OAuth2 password flow: `username` is the email address."""
    user = service.authenticate(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/users", response_model=list[UserOut], dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return service.list_users(db)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    try:
        return service.create_user(db, **payload.model_dump())
    except service.DuplicateUserError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    if user_id == admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    user = service.set_active(db, user_id, payload.is_active)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} was not found.")
    return user
