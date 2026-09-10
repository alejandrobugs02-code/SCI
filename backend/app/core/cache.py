"""Caché en memoria con TTL para los endpoints de lectura pesados.

Con decenas de miles de clientes, recalcular la analítica (escaneos O(n) en Python) en cada
poll del dashboard satura el backend. Estas vistas cambian solo cuando hay una
escritura (envío, ejecución, edición), así que se cachean unos segundos y se
invalidan explícitamente al escribir.
"""
import time
from functools import wraps

_store: dict[str, tuple[float, object]] = {}


def cached(key: str, ttl: float, fn):
    """Devuelve el valor cacheado de `key` o ejecuta `fn()` si expiró/no existe."""
    hit = _store.get(key)
    now = time.time()
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _store[key] = (now, val)
    return val


def ttl_cache(key: str, ttl: float):
    """Decorador para cachear el resultado de un handler (ignora sus argumentos).

    La vista es global (toda la tabla), así que no se cachea por usuario. Usa
    `functools.wraps` para preservar la firma y que FastAPI siga inyectando las
    dependencias (Session, etc.).
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return cached(key, ttl, lambda: fn(*args, **kwargs))
        return wrapper
    return deco


def clear() -> None:
    """Invalida toda la caché (llamar tras cualquier escritura de datos)."""
    _store.clear()
