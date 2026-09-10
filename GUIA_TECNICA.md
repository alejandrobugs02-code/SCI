# SCI · Sistema de Cobranzas Inteligente

MVP de cobranza multicanal que decide cada contacto con **incrementalidad (uplift)**
—contactar a quien el contacto *hace pagar*, y **suprimir** a quien pagaría igual o no
reaccionaría— y, cuando hay que contactar, usa una **escalera de costo creciente**
(WhatsApp → SMS → Voz AI → llamada humana → visita), respetando la normativa peruana de
cobranza (Indecopi Ley 29571, Ley 29733).

- **Backend:** Python · FastAPI
- **Frontend:** React + Vite + TypeScript + Tailwind (dashboards + asistente IA)
- **Canales:** WhatsApp Cloud API · SMS (Twilio) · Voz AI (Vapi) · LLM (Gemini / Groq / OpenAI)
- **Decisión:** motor de uplift por canal, con la escalera de costo como respaldo
  cuando faltan esos datos.
- **Datos:** cartera demo de **100 clientes sintéticos** con uplift (`data/deudores.csv`);
  opcionalmente se puede cargar una cartera real vía ETL.

> ¿Sin presupuesto? Todo el end-to-end (WhatsApp + SMS + Voz AI + LLM) se puede
> probar con **~$0** combinando tiers gratis y créditos de prueba. Ver
> [APIs, proveedores y costos](#apis-proveedores-y-costos).

> 📐 **Estrategia de negocio:** [ESTRATEGIA.md](ESTRATEGIA.md) ·
> **Arquitectura y detalle técnico:** [ARQUITECTURA.md](ARQUITECTURA.md) ·
> **Backlog de producto (118 historias de usuario):**
> [docs/Historias_de_Usuario_SCI.xlsx](docs/Historias_de_Usuario_SCI.xlsx)
> (se regenera con `python docs/generar_historias_usuario.py`) ·
> **Requerimientos (ERS, 101 RF + 66 RNF):**
> [docs/Requerimientos_SCI.docx](docs/Requerimientos_SCI.docx)
> (se regenera con `python docs/generar_requerimientos.py`).

---

## Estructura

```
sci/
├── backend/
│   ├── app/
│   │   ├── main.py            # arranque FastAPI + CORS + lifespan (+ warm-cache)
│   │   ├── models.py          # SQLModel (Deudor con uplift, Contacto…) + carga CSV/XLSX
│   │   ├── core/
│   │   │   ├── config.py      # variables de entorno (.env)
│   │   │   ├── compliance.py  # horarios/feriados permitidos (Indecopi 62b)
│   │   │   ├── nba.py         # economía de canales (costo/tasa de pago)
│   │   │   ├── uplift.py      # motor de incrementalidad (a quién contactar / suprimir)
│   │   │   ├── orchestrator.py# asignación de canal (uplift ó escalera) + plan de campaña
│   │   │   ├── execution.py   # 3 colas concurrentes + gestión humana + suprimidos
│   │   │   ├── cache.py       # caché en memoria con TTL (escala a decenas de miles)
│   │   │   └── scheduler.py   # APScheduler (zona Lima)
│   │   ├── routers/           # auth · strategy · orchestrator · campaign · analytics · assistant · config · deudores · whatsapp · sms · voice
│   │   └── services/          # whatsapp · twilio_sms · vapi · llm (Gemini/Groq/OpenAI)
│   ├── scripts/
│   │   ├── generar_cartera_demo.py   # genera la cartera demo (100 clientes sintéticos)
│   │   └── preparar_datos_reales.py  # ETL opcional: cartera real (3 tablas) → CSV con uplift
│   ├── data/
│   │   └── deudores.csv       # cartera demo: 100 clientes sintéticos con uplift y teléfono
│   ├── .env.example
│   └── requirements.txt
├── docs/                      # backlog (historias de usuario, Excel) + ERS (requerimientos, Word)
└── frontend/                  # Vite + React + Tailwind (+ asistente IA flotante)
```

---

## Requisitos

Ya instalados en esta máquina: **Python 3.13**, **Node 22**, **npm 11**, **Git**.

Para el demo necesitarás además un **túnel** para exponer el webhook
(**Cloudflare Tunnel** gratis y con URL estable, o **ngrok**), y cuentas en los
proveedores de cada canal: **Meta for Developers** (WhatsApp), **Twilio** (SMS),
**Vapi** (Voz AI) y un **LLM** (Gemini gratis / Groq / OpenAI). Todas tienen un
camino de prueba gratis; ver [APIs, proveedores y costos](#apis-proveedores-y-costos)
y `backend/.env.example`.

---

## Puesta en marcha

### 1) Backend (FastAPI)

```powershell
cd backend
# El entorno virtual ya está creado en .venv con las dependencias instaladas.
# Si necesitas recrearlo:
#   python -m venv .venv
#   .\.venv\Scripts\pip install -r requirements.txt

# Configura tus credenciales:
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000  # luego edita .env

# Arranca la API (recarga en caliente):
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Docs interactivas (Swagger): http://localhost:8000/docs

En el primer arranque se crea `sci.db` (SQLite) y se siembra la **cartera demo**
desde `data/deudores.csv`: **100 clientes sintéticos** con incrementalidad (uplift)
por canal, teléfono y documento. Ningún dato proviene de una cartera real.

### 1.b) Regenerar la cartera demo

La cartera se genera con una semilla fija, así que es reproducible:

```powershell
cd backend
# Regenera data/deudores.csv (100 clientes con uplift por canal)
.\.venv\Scripts\python -m scripts.generar_cartera_demo

# Variantes:
#   --n 250        otro tamaño de cartera
#   --semilla 42   otra semilla (otra cartera igual de realista)
#   --recargar     además reemplaza la cartera y la actividad en la base
```

Perfil de la cartera: mora repartida en los cinco tramos (al día, 1–30, 31–60,
61–90, >90), riesgo correlacionado con la mora, disponibilidad de canal ligada al
perfil digital, los cuatro segmentos causales (persuadible, seguro, perdido,
neutro) y algunos casos de opt-out / sin consentimiento para ver las exclusiones.

> ⚠️ Los teléfonos son secuenciales de prueba (`+5198710xxxx`) y **no corresponden
> a personas reales**. Antes de desactivar el modo *Simular*, reemplázalos por
> números propios desde **Base de datos → editar**.

### 1.c) (Opcional) Cargar una cartera real — ETL

Si dispones de una cartera real en tres tablas (clientes, créditos y contactos),
colócalas en `datos previos/` —carpeta gitignoreada, no incluida en el repo— y
genera la cartera con incrementalidad por canal:

```powershell
cd backend
# Cruza las 3 tablas y calcula uplift_{whatsapp,sms,llamada,campo}, prob_pago_base,
# cuota_mensual y fatiga. Escribe data/clientes_reales.csv y recarga la base.
.\.venv\Scripts\python -m scripts.preparar_datos_reales

# Variantes:
#   --solo-csv          genera el CSV sin tocar la base
#   --limite 5000       muestra (semilla fija) que conserva la distribución
```

Si `data/clientes_reales.csv` existe, el backend lo prefiere sobre la cartera demo.
Tras recargar, **reinicia el backend**. Tanto `datos previos/` como
`clientes_reales.csv` están gitignoreados (pesados y confidenciales).

### 2) Frontend (dashboard)

```powershell
cd frontend
npm install      # solo la primera vez
npm run dev
```

- App web: http://localhost:5173 (hace proxy de `/api` al backend)

### Acceso (usuarios demo)

Al entrar a la app **siempre se empieza por `/login`**: cualquier ruta sin sesión
redirige al inicio de sesión. Las credenciales **ya no se muestran en la pantalla
de login** (por seguridad); quedan documentadas solo aquí:

| Rol | Usuario | Contraseña | Puede ver |
|---|---|---|---|
| Super Administrador | `admin` | `admin123` | Dashboards, Base de datos y **Configuración** |
| Usuario Visor | `visor` | `visor123` | Dashboards y Base de datos (sin Configuración) |

> Cámbialas antes de cualquier despliegue real (se crean en `core/security.seed_usuarios`).

### Páginas

- **/login** — autenticación (JWT).
- **/** — Dashboards **sobre datos reales** (se cargan al entrar / recargar, sin polling
  continuo): **Mapa de persuadibles** (uplift: a contactar vs. suprimidos), resultados de la
  campaña (contactados, respuesta, **intención de pago**, costo por conversión), efectividad
  real por canal, GAP por canal, cartera/portafolio (riesgo, mora, región, monto en riesgo),
  priorización accionable (a quién seguir / falta contactar) y la **proyección** de la
  estrategia (estimado del orquestador). Banner Indecopi. Al cargar, sincroniza en segundo
  plano los resultados de las llamadas de Voz (Vapi).
- **/base-datos** — tabla de clientes **paginada** con búsqueda, acciones de envío
  (SMS / WhatsApp / Voz IA), **alta manual de cliente**, edición, **importación XLSX/CSV**,
  **Ejecutar estrategias** (ver abajo) y **reiniciar la actividad** del demo.
- **/configuracion** — umbrales del orquestador, economía de canales y prompts (solo admin).
- **Asistente IA "SCI IA"** — botón flotante en todo el panel: un analista que lee los KPIs
  reales en vivo y responde preguntas del equipo ("¿qué canal rinde más?", "¿a quién priorizo?")
  y guía la navegación. Usa el mismo LLM configurado en `.env`.

### Ejecutar estrategias (automatización)

En **Base de datos** el admin tiene el botón **Ejecutar estrategias**. El orquestador
decide la acción de cada cliente (motor de uplift si hay datos; escalera de costo si no)
y reparte el trabajo así:

- **Canales automatizables** (WhatsApp · SMS · Voz AI) → se ejecutan en **3 colas que
  corren a la vez** (una por canal). Dentro de cada cola se procesa **en orden de
  prioridad por puntaje** (mayor riesgo, monto y mora primero) y con un **throttle**
  entre envíos para **no saturar** al servidor ni a los proveedores.
- **Llamada humana y visita de campo** → **no se automatizan**. En su lugar se genera un
  **reporte CSV descargable** (`reporte_gestion_humana.csv`) con los datos de las personas
  que requieren esa gestión (ID, nombre, documento, teléfono, monto, mora, riesgo, zona,
  acción y motivo), listo para asignar a un gestor.
- **Suprimidos (uplift)** → clientes a los que contactar **no aporta pago incremental**
  (pagarían igual o no reaccionarían): se cuentan y se dejan fuera para ahorrar sin perder
  recupero.
- **Opt-out / sin consentimiento** → excluidos de la campaña.

El resumen de la ejecución reporta, por separado, lo enviado por cola, la gestión humana,
los **suprimidos** y los **excluidos**. Para volver a empezar un demo desde cero, usa
**reiniciar la actividad** (borra contactos/mensajes/promesas, conserva la cartera).

El checkbox **Simular** (activado por defecto) registra los envíos **sin consumir
créditos** ni llamar a las APIs, para ver el efecto en los dashboards/GAP. Desactívalo
para disparar los envíos **reales**. La ejecución respeta la ventana de contacto
(Indecopi): fuera de horario responde **409**.

### Importar la base de datos (XLSX/CSV)

Desde **Base de datos → Importar XLSX** (rol admin). El importador es flexible: usa
las columnas que existan y hace upsert por `cliente_id`. Columnas reconocidas:

```
cliente_id, edad, genero, region, zona, tipo_cliente, es_digital, uso_app,
uso_whatsapp, interaccion_digital_score, canal_whatsapp, canal_sms, canal_llamada,
canal_campo, score_riesgo, prob_default, num_atrasos_previos, dias_mora_promedio,
ratio_pago, ultimo_pago_dias

# Incrementalidad (opcional; las genera el ETL, activan el motor de uplift):
tiene_uplift, prob_pago_base, cuota_mensual, num_contactos_ult7d,
uplift_whatsapp, uplift_sms, uplift_llamada, uplift_campo
```

Derivados automáticamente: `dias_mora` ← `dias_mora_promedio`, `riesgo` ← `score_riesgo`,
disponibilidad de canal ← `canal_*`. Si la fila trae `tiene_uplift=true` y los `uplift_*`,
el orquestador decide por **incrementalidad**; si no, por la **escalera de costo** por mora.
Los campos para envío que el dataset no trae (`nombre`, `telefono`, `monto_deuda`) se
completan a mano en la tabla (botón editar).

---

## Endpoints principales

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/api/auth/login` · GET `/api/auth/me` | — / usuario | Login JWT / usuario actual |
| GET  | `/` | — | Health + ventana de contacto permitida |
| GET  | `/api/strategy/deudores` (paginado) · `/cartera` · `/canales` | usuario | Deudores+canal (`{items,total}`), cartera mora×canal, economía |
| GET  | `/api/orchestrator/plan` | usuario | Plan de campaña + ahorro (proyección) |
| GET  | `/api/analytics/resumen` · `/canales` · `/cartera` · `/segmentos` · `/priorizacion` | usuario | Dashboards reales (KPIs, efectividad, portafolio, **uplift**, prioridades) |
| POST | `/api/assistant/chat` | usuario | Asistente IA del panel (responde con KPIs en vivo) |
| GET  | `/api/campaign/metricas` | usuario | GAP en vivo (embudo por canal) + gasto mensual |
| POST | `/api/campaign/enviar` | usuario | Enviar a un deudor por canal (real) |
| POST | `/api/campaign/ejecutar` | **admin** | Ejecuta estrategias en 3 colas (`{simular}`) |
| POST | `/api/campaign/reset` | **admin** | Reinicia la actividad (conserva la cartera) |
| GET  | `/api/campaign/reporte-gestion-humana` | **admin** | CSV de clientes para llamada humana / visita |
| POST | `/api/voz/llamar` · `/api/voz/sync` | usuario | Lanzar llamada / traer resultados de Vapi (avanza el embudo) |
| POST | `/api/deudores` · PUT `/api/deudores/{id}` | **admin** | Alta manual / editar datos del cliente |
| POST | `/api/deudores/importar` | **admin** | Importar XLSX/CSV |
| GET/PUT | `/api/config` | **admin** | Umbrales + economía de canales + prompts |
| GET/POST | `/webhook/whatsapp` | — | Verificación + estados + mensajes |

Auth: enviar `Authorization: Bearer <token>`. Los webhooks quedan abiertos
(los llaman Meta/Twilio). Todos los envíos pasan por `compliance.esta_permitido()`:
fuera del horario 07:00–20:00 (L–S) o en domingo/feriado peruano responden **409**.

---

## APIs, proveedores y costos

El backend está preparado para dos configuraciones. Elige según tu objetivo y
copia las variables a `backend/.env` (plantilla en `backend/.env.example`).

### Stack "Demo $0" (probar gratis)

Pensado para validar el end-to-end sin desembolso, combinando tiers gratis y
créditos de prueba. Es lo que viene **por defecto** en la config.

| Componente | Proveedor gratis | Variables clave | Nota |
|---|---|---|---|
| **LLM** | **Google Gemini Flash** (sin tarjeta) | `LLM_PROVIDER=gemini`, `LLM_API_KEY`, `LLM_MODEL=gemini-2.5-flash` | Alternativa: `LLM_PROVIDER=groq` (Llama, muy rápido) |
| **WhatsApp** | Número de prueba de **Meta** (Cloud API) | `WA_ACCESS_TOKEN`, `WA_PHONE_NUMBER_ID`, `WA_VERIFY_TOKEN` | Hasta 5 destinatarios registrados; gratis |
| **SMS** | **Twilio Free Trial** (~$15 crédito) | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM` | Solo a números verificados; SMS Perú ~$0.25/seg |
| **Voz AI** | **Vapi** ($10 crédito) | `VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, `VAPI_PHONE_NUMBER_ID` | ~40–90 min reales; es lo primero que se agota |
| **Túnel** | **Cloudflare Tunnel** (gratis, URL estable) | — | Mejor que ngrok free (sin límite de ancho de banda) |

> La **voz** es el cuello de botella de costo: limita las llamadas de prueba a unas
> pocas de 2–3 min. Para iterar sin gastar nada, deja el checkbox **Simular**
> activado en *Ejecutar estrategias*.

### Stack "Mejores resultados" (recomendado)

Cuando quieras la mejor calidad para el demo final (gasto mínimo ~$20–40):

| Componente | Proveedor recomendado | Variables clave |
|---|---|---|
| **LLM** | **OpenAI** `gpt-4o-mini` (o Claude Haiku) — mejor español financiero | `LLM_PROVIDER=openai`, `LLM_API_KEY` (u `OPENAI_API_KEY`), `LLM_MODEL=gpt-4o-mini` |
| **WhatsApp** | **Cloud API con número propio** (sin BSP); plantillas **utility** baratas | mismas variables `WA_*` con número verificado |
| **SMS** | **Twilio** de pago (sin prefijo trial ni límite 50/día) | mismas variables `TWILIO_*` |
| **Voz AI** | **Vapi/Retell + voz de ElevenLabs** (español latino natural) | `VAPI_*` con assistant que use ElevenLabs |
| **Túnel** | **Cloudflare Tunnel** (o ngrok de pago) con dominio propio | — |

> Verifica **siempre** los precios en vivo en las páginas oficiales: cambian seguido
> (Meta WhatsApp por trimestre; OpenAI/Gemini varias veces al año).

### El LLM es intercambiable (un solo cliente)

Gemini, Groq y OpenAI hablan la **misma API de chat de OpenAI**, así que solo cambian
`LLM_PROVIDER`, `LLM_MODEL` y `LLM_API_KEY`; el `base_url` se deriva del proveedor
(o se fuerza con `LLM_BASE_URL`). El código vive en `app/services/llm.py`.

```ini
# Gratis (sin tarjeta):
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
LLM_API_KEY=tu_api_key_de_google_ai_studio

# Mejores resultados:
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o-mini
# LLM_API_KEY=sk-...
```

### Exponer el webhook (túnel)

WhatsApp/Twilio necesitan una URL pública para el webhook. **Recomendado: Cloudflare
Tunnel** (gratis, URL estable, sin interstitial):

```powershell
cloudflared tunnel --url http://localhost:8000
```

Alternativa con ngrok (tier free recortado en 2026: 1 GB/mes, dominio aleatorio):

```powershell
ngrok http 8000
```

Con la URL pública, configura en Meta el webhook `https://<tu-url>/webhook/whatsapp`
con el mismo `WA_VERIFY_TOKEN`, y crea/aprueba una plantilla **utility**
`recordatorio_pago`.

### WhatsApp sin API oficial (neonize) — solo para pruebas

Si no puedes habilitar la API oficial, hay un proveedor alterno vía
[**neonize**](https://github.com/krypton-byte/neonize) (WhatsApp Web no oficial).
Se activa con `WA_PROVIDER=neonize` y **no necesita túnel ni webhook**: conecta por
un socket persistente con login por **QR**.

```powershell
# 1) Instala la dependencia
.\.venv\Scripts\pip install neonize
# 2) Pon WA_PROVIDER=neonize en .env y arranca el backend
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
# 3) Escanea el QR que aparece en ESTA terminal (WhatsApp ▸ Dispositivos vinculados)
```

Tras vincular, los envíos salen como **texto libre** (sin plantillas) y los mensajes
entrantes los responde el mismo bot LLM. La sesión se guarda en `sci_wa.db` (local,
gitignoreado).

> ⚠️ **Riesgo de baneo.** Esto usa WhatsApp Web de forma no oficial, contra los
> Términos de Meta (que desde ene-2026 prohíben bots de IA de terceros). Úsalo solo
> con un **número de prueba**, nunca con el de producción. Para el demo real /
> producción, vuelve a `WA_PROVIDER=cloud` (API oficial).

---

## Bot conversacional (WhatsApp) y captura de datos

El agente de WhatsApp (LLM) no solo responde: alimenta los dashboards con datos reales.

- **Memoria por conversación**: recuerda el hilo (no vuelve a saludar ni pierde contexto).
- **Clasificación de cada mensaje** (`PAGO` / `CIERRE` / `OTRO`): detecta **intención de
  pago** (avanza el contacto a `intencion_pago`) y **cierre** (se despide y deja de responder).
- **Promesas de pago**: extrae **monto + fecha** de lo que dice el cliente y las persiste
  (tabla `Promesa`) → alimenta la priorización y los KPIs.
- **Conversaciones persistidas** (tabla `Mensaje`) para análisis posterior.
- **Reglas de contacto**: solo responde a quien el bot ya contactó (no a chats en frío) y
  resuelve el **LID** de WhatsApp al teléfono real. Configurable: `WA_GRACIA_SEGUNDOS`.

Estados del contacto (embudo): `enviado → entregado → leido → respondido → intencion_pago
→ pagado` (`fallido` aparte). Los recibos de WhatsApp (entregado/leído) los procesa neonize.
La **Voz AI** avanza el embudo por *polling* a Vapi (`/voz/sync`: contestada → `entregado`,
intención → `intencion_pago` + promesa), sin necesidad de webhook. El **SMS** se queda en
`enviado` (los webhooks de estado de Twilio no están conectados).

> 📐 **Arquitectura completa y detalle técnico:** ver [ARQUITECTURA.md](ARQUITECTURA.md).

---

## Cumplimiento (no es asesoría legal)

- **Indecopi (Ley 29571, Art. 62b):** prohibido contactar 20:00–07:00 y
  sábados/domingos/feriados. Implementado en `core/compliance.py`.
- **Ley 29733 (datos personales):** consentimiento para tratar datos y grabar voz;
  registrar opt-out. El modelo `Deudor` incluye `consentimiento` y `opt_out`.
- Incluir disclosure de "agente automatizado / llamada grabada" al inicio de las
  llamadas de Voz AI. Validar todo con el área legal de la entidad antes de producción.

> Las tarifas y tasas del dataset son inputs de referencia, no verificados.
> La tasa de pago de Voz AI es un estimado a validar en campo.
