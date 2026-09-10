"""Login (JWT) y datos del usuario autenticado."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..core.security import crear_token, get_current_user, verify_password
from ..models import Usuario, get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = session.exec(select(Usuario).where(Usuario.username == form.username)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
    token = crear_token(user.username, user.rol)
    return {
        "access_token": token,
        "token_type": "bearer",
        "rol": user.rol,
        "nombre": user.nombre,
        "username": user.username,
    }


@router.get("/me")
def me(user: Usuario = Depends(get_current_user)):
    return {"username": user.username, "nombre": user.nombre, "rol": user.rol}
