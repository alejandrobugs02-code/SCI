"""Autenticación y autorización: hashing de contraseñas, JWT y dependencias de rol."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from .config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# --- Contraseñas ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


# --- Tokens JWT ---
def crear_token(username: str, rol: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "rol": rol, "exp": expira}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# --- Dependencias ---
def get_current_user(token: str = Depends(oauth2_scheme)):
    from ..models import Usuario, engine  # import diferido para evitar ciclos

    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if not username:
            raise cred_exc
    except jwt.PyJWTError:
        raise cred_exc

    with Session(engine) as session:
        user = session.exec(select(Usuario).where(Usuario.username == username)).first()
    if not user:
        raise cred_exc
    return user


def require_admin(user=Depends(get_current_user)):
    if user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta sección requiere rol administrador.",
        )
    return user


def seed_usuarios() -> None:
    """Crea los usuarios demo (admin/usuario) si la tabla está vacía."""
    from ..models import Usuario, engine

    with Session(engine) as session:
        if session.exec(select(Usuario)).first():
            return
        session.add(Usuario(
            username="admin", nombre="Administrador",
            hashed_password=hash_password("admin123"), rol="admin",
        ))
        session.add(Usuario(
            username="visor", nombre="Usuario Visor",
            hashed_password=hash_password("visor123"), rol="usuario",
        ))
        session.commit()
