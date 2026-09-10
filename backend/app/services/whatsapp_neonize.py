"""Proveedor NO oficial de WhatsApp vía neonize (WhatsApp Web).

⚠️ SOLO PARA PRUEBAS. Usa WhatsApp Web de forma no oficial (contra los Términos
de Meta): el número puede ser baneado. Para producción usa la API oficial
(`services/whatsapp.py`). Se activa con `WA_PROVIDER=neonize`.

Login por **QR** (se imprime en la terminal la primera vez); la sesión queda
guardada en un archivo local, así que **no hace falta túnel ni webhook**: la
conexión es un socket saliente persistente. Al recibir un mensaje, reutiliza el
bot LLM (`services/llm`) y avanza el `Contacto` a "respondido", igual que el
webhook oficial.
"""
from __future__ import annotations

import threading

from sqlmodel import Session, select

from ..core.config import settings
from ..core.contactos import rank

_cliente = None
_hilo: threading.Thread | None = None
_lock = threading.Lock()

# Memoria de conversación por número (en memoria; se limpia al reiniciar).
_HISTORIAL: dict[str, list[dict]] = {}
_HIST_MAX = 12  # nº de turnos recientes (user+assistant) que se conservan

# Conversaciones cerradas: si el cliente vuelve a escribir, ya no se le responde
# (hasta que el bot inicie una nueva campaña hacia ese número).
_CERRADAS: set[str] = set()


def _clave(numero: str) -> str:
    """Clave normalizada por número (últimos 9 dígitos), tolerante a formatos."""
    return "".join(ch for ch in numero if ch.isdigit())[-9:]


def _bot_inicio(numero: str) -> bool:
    """True si el bot YA inició conversación con este número (existe un Contacto)."""
    from ..models import Contacto, buscar_deudor_por_telefono, engine

    with Session(engine) as session:
        deudor = buscar_deudor_por_telefono(session, numero)
        if not deudor:
            return False
        return session.exec(
            select(Contacto).where(Contacto.deudor_id == deudor.id)
        ).first() is not None


def _numeros_candidatos(src) -> list[str]:
    """Posibles números del remitente. WhatsApp puede direccionar por LID (un id
    anónimo) en vez del teléfono; el teléfono real suele venir en SenderAlt."""
    cands: list[str] = []
    for jid in (getattr(src, "Sender", None), getattr(src, "SenderAlt", None),
                getattr(src, "Chat", None)):
        u = getattr(jid, "User", "") if jid is not None else ""
        if u and u not in cands:
            cands.append(u)
    return cands


def _resolver_numero(src) -> str:
    """Elige el candidato que corresponde a un deudor (resuelve el LID al teléfono)."""
    from ..models import buscar_deudor_por_telefono, engine

    candidatos = _numeros_candidatos(src)
    with Session(engine) as session:
        for c in candidatos:
            if buscar_deudor_por_telefono(session, c):
                return c
    return candidatos[0] if candidatos else ""


def _esperar_inicio(numero: str) -> bool:
    """Espera una gracia configurable a que exista el contacto antes de ignorar."""
    import time as _time

    if _bot_inicio(numero):
        return True
    fin = _time.monotonic() + max(0, settings.wa_gracia_segundos)
    while _time.monotonic() < fin:
        _time.sleep(0.5)
        if _bot_inicio(numero):
            return True
    return False


def _avanzar_por_id(message_ids: list[str], nuevo: str) -> None:
    """Avanza el Contacto cuyo detalle (id de mensaje) coincida (recibos)."""
    from ..models import Contacto, engine

    ids = [m for m in message_ids if m]
    if not ids:
        return
    with Session(engine) as session:
        for mid in ids:
            c = session.exec(
                select(Contacto).where(Contacto.detalle == mid).order_by(Contacto.id.desc())
            ).first()
            if c and rank(nuevo) > rank(c.estado):
                c.estado = nuevo
                session.add(c)
        session.commit()


def _texto_entrante(message) -> str:
    """Extrae el texto de un mensaje entrante (texto simple o con contexto)."""
    msg = message.Message
    return (msg.conversation or msg.extendedTextMessage.text or "").strip()


def _guardar_promesa(session, deudor_id: int, texto: str) -> None:
    """Extrae una promesa de pago del mensaje y la persiste (si hay)."""
    from datetime import date as _date

    from ..models import Promesa
    from . import llm

    p = llm.extraer_promesa(texto)
    if not (p["monto"] or p["fecha_texto"]):
        return
    fecha = None
    try:
        fecha = _date.fromisoformat(p["fecha"]) if p["fecha"] else None
    except (ValueError, TypeError):
        fecha = None
    session.add(Promesa(
        deudor_id=deudor_id, monto=p["monto"] or 0.0,
        fecha_texto=p["fecha_texto"], fecha=fecha,
    ))


def _responder_bot(numero: str, texto: str, nombre_wa: str) -> tuple[str, bool]:
    """Genera la respuesta del bot y devuelve (respuesta, cerrar_conversacion)."""
    from ..models import (
        Contacto,
        Mensaje,
        buscar_deudor_por_telefono,
        engine,
        get_or_create_config,
    )
    from . import llm

    nombre = nombre_wa
    monto = None
    deudor_id = None
    # Clasifica el mensaje: PAGO (intención), CIERRE (despedida) u OTRO.
    etiqueta = llm.clasificar_mensaje(texto)
    cerrar = etiqueta == "CIERRE"
    nuevo_estado = "intencion_pago" if etiqueta == "PAGO" else "respondido"
    with Session(engine) as session:
        deudor = buscar_deudor_por_telefono(session, numero)
        prompt = get_or_create_config().prompt_whatsapp or None
        if deudor:
            deudor_id = deudor.id
            nombre = deudor.nombre or nombre_wa
            monto = deudor.monto_deuda
            contacto = session.exec(
                select(Contacto)
                .where(Contacto.deudor_id == deudor.id)
                .order_by(Contacto.id.desc())
            ).first()
            if contacto and rank(nuevo_estado) > rank(contacto.estado):
                contacto.estado = nuevo_estado
                session.add(contacto)
            if etiqueta == "PAGO":  # registra el compromiso de pago
                _guardar_promesa(session, deudor.id, texto)
        # Persiste el mensaje entrante del cliente (para análisis).
        session.add(Mensaje(deudor_id=deudor_id, canal="whatsapp", rol="cliente", texto=texto))
        session.commit()

    # Memoria: pasa los turnos previos para que no vuelva a saludar ni pierda hilo.
    historial = _HISTORIAL.setdefault(_clave(numero), [])
    respuesta = llm.responder(
        texto, nombre=nombre, monto=monto, system_prompt=prompt,
        historial=historial, cerrar=cerrar,
    )
    historial.append({"role": "user", "content": texto})
    historial.append({"role": "assistant", "content": respuesta})
    del historial[:-_HIST_MAX]  # conserva solo los últimos turnos

    # Persiste la respuesta del bot.
    with Session(engine) as session:
        session.add(Mensaje(deudor_id=deudor_id, canal="whatsapp", rol="bot", texto=respuesta))
        session.commit()
    return respuesta, cerrar


# Valores del enum ReceiptType de neonize.
_RECIBO_DELIVERED, _RECIBO_READ, _RECIBO_PLAYED = 1, 4, 6


def _registrar_eventos(client) -> None:
    from neonize.events import (
        ConnectedEv,
        LoggedOutEv,
        MessageEv,
        PairStatusEv,
        QREv,
        ReceiptEv,
    )

    @client.event(ReceiptEv)
    def _on_receipt(_c, event):  # noqa: ANN001
        # Recibo de NUESTRO mensaje saliente: el cliente lo recibió o lo leyó.
        ids = list(event.MessageIDs)
        if event.Type in (_RECIBO_READ, _RECIBO_PLAYED):
            _avanzar_por_id(ids, "leido")
        elif event.Type == _RECIBO_DELIVERED:
            _avanzar_por_id(ids, "entregado")

    @client.event(QREv)
    def _on_qr(_c, event):  # noqa: ANN001
        import segno

        for code in event.Codes:
            print("\n[WhatsApp/neonize] Escanea este QR (WhatsApp ▸ Dispositivos vinculados):\n")
            segno.make(code).terminal(compact=True)
            break

    @client.event(PairStatusEv)
    def _on_pair(_c, event):  # noqa: ANN001
        print(f"[WhatsApp/neonize] Vinculado como +{event.ID.User}")

    @client.event(ConnectedEv)
    def _on_connected(_c, _event):  # noqa: ANN001
        print("[WhatsApp/neonize] Conectado a WhatsApp.")

    @client.event(LoggedOutEv)
    def _on_logout(_c, _event):  # noqa: ANN001
        print("[WhatsApp/neonize] Sesión cerrada; reescanea el QR al reiniciar.")

    @client.event(MessageEv)
    def _on_message(cli, message):  # noqa: ANN001
        src = message.Info.MessageSource
        if src.IsFromMe or src.IsGroup:  # ignora lo propio y los grupos
            return
        numero = _resolver_numero(src)  # resuelve LID → teléfono real
        texto = _texto_entrante(message)
        print(f"[WhatsApp/neonize] << de {numero} (cands={_numeros_candidatos(src)}): {texto!r}")
        # No responder si la conversación está cerrada, o si el bot nunca le
        # escribió (no inició la conversación: nada de chats en frío).
        if _clave(numero) in _CERRADAS:
            print(f"[WhatsApp/neonize] -- ignorado: conversación cerrada ({_clave(numero)})")
            return
        if not _esperar_inicio(numero):
            print(f"[WhatsApp/neonize] -- ignorado: el bot no inició (sin contacto previo) {_clave(numero)}")
            return
        if not texto:  # sticker, imagen, audio… sin texto que procesar
            cli.send_message(
                src.Chat,
                "¡Hola! Por ahora solo puedo leer mensajes de texto. "
                "¿Me cuentas en qué te ayudo con tu cuota?",
            )
            return
        nombre_wa = message.Info.Pushname or ""
        cerrar = False
        try:
            respuesta, cerrar = _responder_bot(numero, texto, nombre_wa)
            print(f"[WhatsApp/neonize] >> respondiendo (cerrar={cerrar}): {respuesta[:70]!r}")
        except Exception as e:  # noqa: BLE001
            # El error real (p. ej. 429/401 del LLM) queda en la consola del backend.
            print(f"[WhatsApp/neonize] Error procesando mensaje: {type(e).__name__}: {e}")
            respuesta = "Disculpe, tuvimos un inconveniente. En breve le respondemos."
        cli.send_message(src.Chat, respuesta)
        if cerrar:  # el cliente se despidió: cierra y no responde más
            _CERRADAS.add(_clave(numero))


def iniciar() -> None:
    """Arranca el cliente neonize en un hilo de fondo (no bloquea a FastAPI)."""
    global _cliente, _hilo
    with _lock:
        if _hilo and _hilo.is_alive():
            return
        from neonize.client import NewClient

        _cliente = NewClient(settings.wa_neonize_session)
        _registrar_eventos(_cliente)

        def _run():
            try:
                _cliente.connect()  # bloquea: procesa eventos hasta desconectar
            except Exception as e:  # noqa: BLE001
                print(f"[WhatsApp/neonize] Conexión finalizada: {e}")

        _hilo = threading.Thread(target=_run, name="neonize-wa", daemon=True)
        _hilo.start()
        print("[WhatsApp/neonize] Cliente iniciado (esperando QR/conexión)…")


def esta_conectado() -> bool:
    return bool(_cliente is not None and _cliente.is_connected)


def enviar_texto(numero: str, texto: str) -> str:
    """Envía texto libre por WhatsApp Web. Devuelve el ID del mensaje."""
    from neonize.utils import build_jid

    if _cliente is None:
        raise RuntimeError("WhatsApp (neonize) no está iniciado. ¿WA_PROVIDER=neonize?")
    if not _cliente.is_connected:
        raise RuntimeError("WhatsApp (neonize) aún no conecta. Escanea el QR de la terminal.")
    solo_digitos = "".join(ch for ch in numero if ch.isdigit())
    # El bot (re)inicia conversación: reabre si estaba cerrada y limpia la memoria.
    _CERRADAS.discard(_clave(numero))
    _HISTORIAL.pop(_clave(numero), None)
    resp = _cliente.send_message(build_jid(solo_digitos), texto)
    return getattr(resp, "ID", "") or "enviado"
