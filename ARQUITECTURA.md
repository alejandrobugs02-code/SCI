# SCI · Sistema de Cobranzas Inteligente — Arquitectura y documentación técnica

Documento técnico a profundidad del proyecto: qué hace, cómo está construido, cómo
fluye la información y por qué se tomaron las decisiones de diseño. Para la guía de
puesta en marcha y credenciales, ver [README.md](README.md); para el pitch de negocio,
[ESTRATEGIA.md](ESTRATEGIA.md).

---

## Tabla de contenido

1. [Visión general](#1-visión-general)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Arquitectura general](#3-arquitectura-general)
4. [Estructura del repositorio](#4-estructura-del-repositorio)
5. [Modelo de datos](#5-modelo-de-datos)
6. [El motor de decisión: uplift + escalera de costo](#6-el-motor-de-decisión-uplift--escalera-de-costo)
7. [Datos: cartera demo y ETL opcional](#7-datos-cartera-demo-y-etl-opcional)
8. [Backend en detalle](#8-backend-en-detalle)
9. [El bot conversacional de WhatsApp](#9-el-bot-conversacional-de-whatsapp)
10. [El asistente interno "SCI IA"](#10-el-asistente-interno-sci-ia)
11. [Analítica y dashboards](#11-analítica-y-dashboards)
12. [Escala y rendimiento (caché, paginación)](#12-escala-y-rendimiento-caché-paginación)
13. [Frontend en detalle](#13-frontend-en-detalle)
14. [Flujos clave (secuencias)](#14-flujos-clave-secuencias)
15. [Configuración (.env)](#15-configuración-env)
16. [Seguridad, privacidad y cumplimiento](#16-seguridad-privacidad-y-cumplimiento)
17. [Decisiones de diseño y limitaciones](#17-decisiones-de-diseño-y-limitaciones)

---

## 1. Visión general

**SCI** (Sistema de Cobranzas Inteligente) es un MVP de **cobranza multicanal
inteligente** para entidades de microfinanzas. Su núcleo
de decisión combina dos ideas:

1. **Incrementalidad (uplift):** no contactar "a quien va a pagar" sino **a quien el
   contacto hace pagar** (que no pagaría solo). A quien pagaría igual —o no pagaría
   pase lo que pase— se le **suprime**: ahorro sin perder recupero.
2. **Escalera de costo creciente** (next-best-action): cuando hay que contactar, usar
   el canal más barato que funcione, escalando solo cuando es necesario:

```
WhatsApp (IA)  →  SMS  →  Voz IA  →  Llamada humana  →  Visita de campo
  S/0.10        S/0.20    S/0.80       S/1.50            S/8.00
  más barato ───────────────────────────────────────► más caro
```

El sistema:
- **Decide** por cliente: a quién contactar (motor de uplift) y por qué canal
  (escalera de costo como respaldo cuando no hay datos de uplift).
- **Ejecuta** los canales automatizables (WhatsApp, SMS, Voz IA) en colas concurrentes
  con control de carga; para llamada humana y visita genera un **reporte** para gestores.
- **Conversa** por WhatsApp con un agente LLM que detecta intención de pago, registra
  promesas (monto + fecha) y cierra con cortesía.
- **Mide** todo con dashboards de **datos reales**: embudo de engagement, efectividad
  por canal, costo por conversión, cartera en riesgo, mapa de persuadibles y prioridades.
- **Asiste** al equipo con un chat interno ("SCI IA") que lee los KPIs en vivo.
- **Cumple** la normativa peruana de cobranza (Indecopi, Ley 29733).

---

## 2. Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.13 · **FastAPI** · Uvicorn (ASGI) |
| ORM / BD | **SQLModel** (SQLAlchemy + Pydantic) sobre **SQLite** |
| Auth | JWT (`pyjwt`) + hashing `bcrypt` |
| Programador | APScheduler (zona `America/Lima`) |
| Datos / ETL | **pandas** + **openpyxl** (cartera demo sintética · ETL opcional de 3 tablas) |
| LLM | Cliente `openai` apuntando a **Gemini / Groq / OpenAI** (API compatible) |
| WhatsApp | **Cloud API (Meta)** vía Graph, o **neonize** (WhatsApp Web no oficial) |
| SMS | **Twilio** |
| Voz IA | **Vapi** (orquestación de voz; resultados por polling a su API) |
| Frontend | **React 18** · **Vite** · **TypeScript** · **Tailwind** · React Router 7 · Recharts · Axios · lucide-react |

---

## 3. Arquitectura general

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (Vite/React)                        │
│  Login · Dashboards (datos reales) · Base de datos · Configuración    │
│  Asistente IA flotante  ·  axios → proxy /api → backend  ·  JWT       │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ HTTP (REST, Bearer JWT)
┌───────────────────────────────▼─────────────────────────────────────┐
│                          BACKEND (FastAPI)                            │
│                                                                       │
│  Routers:  auth · strategy · orchestrator · campaign · analytics      │
│            assistant · config · deudores · whatsapp · sms · voice     │
│                                                                       │
│  Core:     config · security · compliance · nba · orchestrator        │
│            uplift · execution · contactos · cache · scheduler          │
│                                                                       │
│  Services: llm (Gemini/Groq/OpenAI) · whatsapp (Cloud) ·              │
│            whatsapp_neonize (WhatsApp Web) · twilio_sms · vapi         │
│                                                                       │
│  Modelos (SQLModel):  Deudor · Contacto · Mensaje · Promesa ·         │
│                       Usuario · AppConfig          →  SQLite (sci.db)│
│                                                                       │
│  Scripts (offline):  generar_cartera_demo.py · preparar_datos_reales.py│
└───┬───────────────┬───────────────┬───────────────┬──────────────────┘
    │               │               │               │
    ▼               ▼               ▼               ▼
 WhatsApp        Twilio           Vapi          LLM (Groq/
 (Meta/neonize)  (SMS)            (Voz IA)      Gemini/OpenAI)
```

**Principios de diseño:**
- **Decisión causal antes que predictiva**: el motor de uplift decide a quién mueve el
  contacto; la escalera de costo es el respaldo cuando faltan esos datos.
- **Proveedores intercambiables** por configuración (LLM y WhatsApp) sin tocar la lógica.
- **Separación lógica pura / I/O**: `core/*` contiene reglas testeables (uplift,
  asignación de canal, embudo, planificación) sin efectos secundarios; los
  `routers/services` hacen el I/O.
- **Datos reales como fuente de verdad**: los dashboards leen la bitácora de `Contacto`,
  `Mensaje` y `Promesa`, no supuestos.
- **Pensado para volumen**: caché con TTL + paginación para operar con decenas de miles
  de clientes sin saturar el backend.

---

## 4. Estructura del repositorio

```
sci/
├── backend/
│   ├── app/
│   │   ├── main.py            # arranque FastAPI: CORS + lifespan (init_db, seed,
│   │   │                      # scheduler, warm-cache, neonize) + montaje de routers
│   │   ├── models.py          # tablas SQLModel + carga CSV/XLSX + helpers de datos
│   │   ├── core/
│   │   │   ├── config.py      # Settings (pydantic-settings, lee .env)
│   │   │   ├── security.py    # bcrypt, JWT, dependencias de rol, seed de usuarios
│   │   │   ├── compliance.py  # ventana de contacto Indecopi (configurable)
│   │   │   ├── nba.py         # catálogo de canales + valor esperado
│   │   │   ├── uplift.py      # motor de incrementalidad (a quién contactar / suprimir)
│   │   │   ├── orchestrator.py# asignación de canal (uplift ó reglas) + plan + cartera
│   │   │   ├── execution.py   # planificación de colas (automatizable/humano/suprimido)
│   │   │   ├── contactos.py   # estados del embudo y su jerarquía (rank)
│   │   │   ├── cache.py       # caché en memoria con TTL para lecturas pesadas
│   │   │   └── scheduler.py   # APScheduler (zona Lima)
│   │   ├── routers/
│   │   │   ├── auth.py · config.py · deudores.py
│   │   │   ├── strategy.py    # deudores+canal (paginado), cartera, economía
│   │   │   ├── orchestrator.py# proyección del plan (ahorro vs. baseline)
│   │   │   ├── campaign.py    # envíos, ejecución en colas, reset, reporte, GAP
│   │   │   ├── analytics.py   # dashboards reales (resumen, canales, cartera, segmentos…)
│   │   │   ├── assistant.py   # asistente interno "SCI IA"
│   │   │   └── whatsapp.py · sms.py · voice.py # webhooks/envíos por canal
│   │   └── services/
│   │       ├── llm.py             # bot + asistente + clasificador + extractor de promesas
│   │       ├── prompts.py         # system prompts de marca (WhatsApp / Voz)
│   │       ├── whatsapp.py        # Cloud API (Meta) — oficial
│   │       ├── whatsapp_neonize.py# WhatsApp Web (no oficial) — pruebas
│   │       ├── twilio_sms.py · vapi.py
│   ├── scripts/
│   │   ├── generar_cartera_demo.py   # cartera demo: 100 clientes sintéticos con uplift
│   │   └── preparar_datos_reales.py  # ETL opcional: cartera real (3 tablas) → CSV
│   ├── data/
│   │   └── deudores.csv       # cartera demo (100 clientes, con teléfono y uplift)
│   ├── .env / .env.example   # credenciales (real / plantilla)
│   └── requirements.txt
├── docs/                     # backlog de producto (historias de usuario en Excel)
└── frontend/
    └── src/
        ├── main.tsx · App.tsx · auth.tsx · api.ts · format.ts · theme.ts
        ├── pages/    (LoginPage · DashboardPage · BaseDatosPage · ConfiguracionPage)
        └── components/ (paneles de dashboard, AsistenteWidget, layout, rutas, etc.)
```

---

## 5. Modelo de datos

SQLite vía SQLModel. `init_db()` crea las tablas faltantes en cada arranque
(`SQLModel.metadata.create_all`). La BD se siembra desde `data/deudores.csv`
(**cartera demo: 100 clientes sintéticos con uplift**) o, si existe, desde
`clientes_reales.csv` (cartera real cargada vía el ETL opcional).

### `Deudor` — cartera de clientes
Datos de envío (`nombre`, `telefono`, `documento`, `monto_deuda`) + features del dataset
(`edad`, `genero`, `region`, `zona`, `tipo_cliente`, `es_digital`, `uso_app`,
`uso_whatsapp`, `interaccion_digital_score`, disponibilidad por canal
`canal_whatsapp/sms/llamada/campo`, `score_riesgo`, `prob_default`,
`num_atrasos_previos`, `dias_mora_promedio`, `ratio_pago`, `ultimo_pago_dias`) +
derivados (`dias_mora`, `riesgo` ∈ {bajo,medio,alto}, `opt_out`, `consentimiento`).

**Campos de incrementalidad (uplift)** — alimentan el motor causal:
- `tiene_uplift` (bool): si es `True`, el orquestador decide por uplift; si no, cae a la
  escalera de costo por mora.
- `cuota_mensual`: monto recuperable en la ventana de 7 días (si no hay, se usa el saldo).
- `prob_pago_base`: P(paga en 7 días | sin contacto).
- `uplift_whatsapp / uplift_sms / uplift_llamada / uplift_campo`: incremento de prob. de
  pago por canal (`llamada` cubre Voz AI y llamada humana; `campo` → visita).
- `num_contactos_ult7d`: contactos recientes → penalización por fatiga.

### `Contacto` — bitácora auditable de cada contacto (alimenta el GAP)
`deudor_id`, `canal`, `estado`, `costo`, `monto_pagado`, `detalle` (id del mensaje/nota,
o call-id de Vapi), `creado_en`. Es el corazón de la analítica real.

**Estados (embudo) y jerarquía** — `core/contactos.py`:

```
fallido(0) < enviado(1) < entregado(2) < leido(3) < respondido(4)
          < intencion_pago(5) < pagado(6)
```

Un estado solo "avanza" si su `rank` es mayor (no retrocede). `intencion_pago` es la
señal de resultado más fuerte que producen el bot (WhatsApp) y el polling de Vapi (Voz).

### `Mensaje` — conversación persistida (para análisis)
`deudor_id`, `canal`, `rol` ∈ {cliente, bot}, `texto`, `creado_en`.

### `Promesa` — compromiso de pago detectado
`deudor_id`, `monto`, `fecha_texto` ("mañana", "el viernes"), `fecha` (ISO si se pudo
interpretar), `creado_en`. Se extrae del mensaje del cliente con el LLM (WhatsApp) o del
`structuredData` de la llamada de Vapi (Voz).

### `Usuario` — acceso al panel
`username` (único), `nombre`, `hashed_password` (bcrypt), `rol` ∈ {admin, usuario}.

### `AppConfig` — configuración editable (fila única id=1)
Prompts de WhatsApp/Voz, umbrales del orquestador (`dias_temprana/media/tardia`,
`monto_riesgo_temprano`, `monto_voz_humano`, `monto_visita`) y overrides de economía de
canales (`canales_json`).

---

## 6. El motor de decisión: uplift + escalera de costo

La decisión por cliente vive en `core/orchestrator.asignar_canal(deudor, umbrales, canales)`,
que elige una de **dos capas** según `deudor["tiene_uplift"]`:

### 6.1 Capa causal — incrementalidad (`core/uplift.py`)

Cambia la pregunta de *"¿quién va a pagar?"* a *"¿a quién hace pagar el contacto?"*. Para
cada canal disponible calcula el **valor incremental**:

```
valor_esperado(canal) = uplift_canal × monto_recuperable
                       − costo_canal − λ·num_contactos_ult7d   (λ = LAMBDA_FATIGA = 1.0)
```

- Elige el canal de **mayor** valor incremental.
- Si el mejor valor `≤ UMBRAL_NO_CONTACTAR` (0 por defecto) → **acción `no_contactar`
  (supresión)**: el contacto no aporta pago adicional, así que no se gasta.
- Devuelve una `recomendacion` compatible con la del orquestador, más `accion`
  (`contactar` | `no_contactar`), `uplift` y `segmento`.

**Segmentación causal** (`uplift.segmentar`):
- `persuadible` si `mejor_uplift ≥ 0.03` (el contacto mueve el pago).
- `seguro` si `prob_pago_base ≥ 0.60` (paga solo).
- `perdido` si `prob_pago_base ≤ 0.25` (no reacciona).
- `neutro` en otro caso.

### 6.2 Capa de respaldo — escalera de costo (reglas por mora)

Cuando `tiene_uplift` es `False`, aplica el árbol de next-best-action:

```
opt_out                         → ninguno (excluido)
dias_mora <= 0                  → SMS (preventivo)
dias_mora <= dias_temprana      → WhatsApp  (o Voz IA si riesgo alto y monto alto;
                                  o SMS si no tiene WhatsApp)
dias_mora <= dias_media         → Voz IA (o llamada humana si monto alto)
dias_mora <= dias_tardia        → llamada humana
dias_mora >  dias_tardia        → visita (si monto alto) / llamada humana
```

Luego hay **fallback por disponibilidad**: si el canal elegido no está disponible para
ese cliente (`canal_*`), baja al siguiente disponible (`ORDEN_FALLBACK`).

### 6.3 Proyección del plan (`plan_campania`)

Compara el costo de SCI contra el **baseline tradicional** (`asignar_canal_baseline`:
contact center humano para mora ≤90 días + visita para >90 con monto alto, contactando a
**todos** los no-excluidos). Reporta:
- `costo_optimizado` vs. `costo_baseline`, `ahorro_soles`, `ahorro_pct`.
- `recupero_esperado`: para los contactados, `tasa_pago × monto`; **para los suprimidos
  se mantiene el recupero base** (`prob_pago_base × monto`) — pagan sin contacto.
- `deudores_gestionados`, `suprimidos`, `excluidos_opt_out`, `por_canal` y
  `proyeccion_gap` (contactabilidad vs. promesas). **Todo esto es proyección.**

`cartera_mora_canal` da la distribución por tramo de mora × canal asignado.

---

## 7. Datos: cartera demo y ETL opcional

### 7.1 Cartera demo (la que trae el proyecto)

`backend/scripts/generar_cartera_demo.py` genera `backend/data/deudores.csv`:
**100 clientes sintéticos** —ningún registro proviene de una cartera real— calibrados
para que el sistema se comporte como con datos de verdad:

- **Mora** repartida en los cinco tramos (al día 22 · 1–30 32 · 31–60 13 · 61–90 22 · >90 11).
- **Riesgo** (`score_riesgo`, `prob_default`, `ratio_pago`, `num_atrasos_previos`)
  correlacionado con el tramo de mora.
- **Disponibilidad de canal** ligada al perfil digital (zona, edad, uso de app/WhatsApp).
- **Incrementalidad**: todos con `tiene_uplift=True` y los cuatro segmentos causales
  (≈42 persuadibles, 20 seguros, 13 perdidos, 21 neutros), con el canal de mayor uplift
  dependiendo del perfil (digital → WhatsApp; mora alta / no digital → llamada o campo).
- **Cumplimiento**: 4 clientes con opt-out y 2 sin consentimiento, para que se vean las
  exclusiones en la ejecución.

Semilla fija (`20260830`) → la cartera es reproducible. Los teléfonos son secuenciales
de prueba (`+5198710xxxx`) y **no corresponden a personas reales**.

```powershell
python -m scripts.generar_cartera_demo                # regenera el CSV
python -m scripts.generar_cartera_demo --n 250        # otro tamaño
python -m scripts.generar_cartera_demo --recargar     # + recarga la base
```

### 7.2 ETL de una cartera real (opcional)

`backend/scripts/preparar_datos_reales.py` construye la cartera con uplift cruzando
**tres tablas** de origen (clientes, créditos y contactos). No vienen en el repositorio:
deben colocarse en `datos previos/` (gitignored por tamaño y confidencialidad):

```
01_Tabla_de_Clientes  → features demográficas / riesgo / disponibilidad de canal
02_Tabla_de_Créditos  → saldo, cuota, mora real, prob_pago_7d_base (último corte/crédito)
03_Tabla_contactos    → prob_pago_7d_post por canal → uplift, costo, fatiga (~3 min de lectura)
```

Por cada cliente produce: `monto_deuda` (saldo), `cuota_mensual`, `dias_mora` real,
`prob_pago_base`, `uplift_{whatsapp,sms,llamada,campo}` (= post por canal − base; usa la
media global del canal si el cliente no tuvo ese canal), `num_contactos_ult7d` y `riesgo`
recalibrado desde `prob_default`. Genera nombres/documentos sintéticos (los teléfonos se
completan a mano para el envío real). Uso:

```powershell
python -m scripts.preparar_datos_reales              # genera CSV + recarga la base
python -m scripts.preparar_datos_reales --solo-csv   # solo genera el CSV
python -m scripts.preparar_datos_reales --limite 5000 # muestra (semilla fija) que conserva la distribución
```

Escribe `backend/data/clientes_reales.csv` y opcionalmente recarga la base (borra
`Contacto/Mensaje/Promesa/Deudor` y reinserta). `seed_desde_csv()` prefiere ese CSV; si no
existe, usa la cartera demo de 100 clientes.

---

## 8. Backend en detalle

### 8.1 Arranque (`main.py`)
`lifespan`: `init_db()` → `seed_desde_csv()` → `seed_usuarios()` → `get_or_create_config()`
→ arranca el `scheduler` → lanza un **hilo daemon que calienta la caché** (`_warm_cache`:
precalcula resumen/canales/cartera/priorizacion/segmentos/plan/métricas para que el primer
poll del dashboard ya encuentre datos) → si `WA_PROVIDER=neonize`, lanza el cliente de
WhatsApp Web en un hilo de fondo. CORS habilitado para el dev server de Vite (`localhost:5173`).

### 8.2 Configuración (`core/config.py`)
`Settings` (pydantic-settings) lee `.env`. Todo tiene default vacío para que la app
arranque sin credenciales; cada servicio valida su llave solo cuando se usa. Ver
[sección 15](#15-configuración-env).

### 8.3 Autenticación y roles (`core/security.py`)
- Contraseñas con **bcrypt**; tokens **JWT** (HS256, expira en `JWT_EXPIRE_MINUTES`).
- `get_current_user` valida el Bearer y carga el `Usuario`; `require_admin` exige rol admin.
- `seed_usuarios()` crea `admin/admin123` y `visor/visor123` si la tabla está vacía.

### 8.4 Cumplimiento (`core/compliance.py`)
Indecopi (Ley 29571, Art. 62b): prohibido contactar 20:00–07:00 y domingos/feriados.
`esta_permitido()` devuelve `(permitido, motivo)`; los envíos que caen fuera responden
**409**. Configurable por `.env`: `COMPLIANCE_ENABLED` (false para pruebas nocturnas),
`COMPLIANCE_HORA_INICIO/FIN`. Feriados peruanos vía librería `holidays`.

### 8.5 Economía de canales (`core/nba.py`)
`CANALES`: por canal define `costo`, `tasa_pago`, `contactabilidad`, `orden`, `categoria`.
`valor_esperado(canal, monto) = tasa_pago * monto − costo` (usado por la capa de escalera;
la capa de uplift usa su propio valor incremental). La economía es editable desde
Configuración (overrides en `AppConfig.canales_json`, ver `models.canales_actuales`).

### 8.6 Motor de uplift y orquestador
Ver [sección 6](#6-el-motor-de-decisión-uplift--escalera-de-costo). `core/uplift.py`
(incrementalidad/supresión + segmentación) y `core/orchestrator.py` (selección de capa,
plan de campaña, cartera por mora×canal).

### 8.7 Planificación de ejecución (`core/execution.py`)
`planificar(deudores)` devuelve `(colas, gestion_humana, suprimidos, excluidos)`:
- **3 colas automatizables**: `whatsapp`, `sms`, `voz_ai`.
- **Gestión humana**: `llamada_humana`, `visita` (no se automatizan → reporte).
- **Suprimidos**: el motor de uplift decidió `no_contactar` aun teniendo canal.
- **Excluidos**: `ninguno` (opt-out). *La `accion` manda sobre el canal.*

Dentro de cada cola, orden por **prioridad**: `(-score, -monto, -dias_mora)` (el `score`
prefiere `prob_default`, ya en 0–1) → primero el más riesgoso, de mayor monto y más mora.

### 8.8 Router de campaña (`routers/campaign.py`)
- `POST /enviar` — envía a un deudor por un canal (real). Valida opt-out, teléfono y
  ventana de contacto; registra un `Contacto` e invalida la caché.
- `POST /ejecutar` (admin) — corre las **3 colas en paralelo** (`asyncio.gather`); cada cola
  procesa **secuencial** con un **throttle** (`THROTTLE_SEGUNDOS`). `simular` (default true)
  registra envíos sin llamar a las APIs (ilumina dashboards sin gasto). Devuelve también
  `suprimidos` y `excluidos`.
- `POST /reset` (admin) — borra la actividad (Contacto/Mensaje/Promesa) para reiniciar un
  demo, **sin** tocar la cartera ni la configuración.
- `GET /reporte-gestion-humana` (admin) — CSV (con BOM para Excel) de los clientes que
  requieren llamada humana o visita.
- `GET /metricas` — el **GAP** en vivo: embudo global y por canal (acumulativo por `rank`),
  intención, costo y gasto mensual (cacheado 8 s).
- `POST /contacto/{id}/estado` — avance manual del embudo (utilitario).
- WhatsApp saliente se abstrae en `_enviar_whatsapp`: Cloud API (plantilla) o neonize
  (texto libre) según `WA_PROVIDER`.

### 8.9 Router de analítica (`routers/analytics.py`) — datos reales
Todos los handlers van cacheados con TTL ([sección 12](#12-escala-y-rendimiento-caché-paginación)).
- `GET /resumen` — KPIs por **deudor** (mejor estado alcanzado): contactados, respondidos,
  intención, tasas, monto en intención, costo real, **costo por intención**, promesas,
  deuda total.
- `GET /canales` — efectividad **por canal**: embudo, costo y **costo por conversión**.
- `GET /cartera` — portafolio: distribución por riesgo / tramo de mora / región / digital y
  **monto en riesgo** (`Σ prob_default × monto`).
- `GET /segmentos` — **mapa de persuadibles**: segmentación causal de la cartera (persuadible/
  seguro/perdido/neutro), cuántos contactar vs. suprimir, `suprimir_pct`, canal recomendado y
  costo optimizado. Devuelve `{tiene_uplift: false}` si la cartera no tiene datos de uplift.
- `GET /priorizacion` — listas accionables (top 100 por monto): con intención (+ su promesa) y
  alto riesgo sin contactar.

### 8.10 Servicio LLM (`services/llm.py`)
Un solo cliente `openai` con `base_url` derivado del proveedor (`LLM_PROVIDER`):
`gemini` → endpoint OpenAI-compat de Google; `groq` → Groq; `openai` → por defecto. El
cliente se cachea y se recrea si cambia `(api_key, base_url)`. Funciones:
- `responder(...)` — respuesta del **bot de WhatsApp** con memoria (historial) y modo
  despedida (`cerrar`).
- `responder_asistente(mensaje, system_prompt, historial)` — respuesta del **asistente
  interno** del panel (temp 0.3, memoria acotada a 10 turnos); ver [sección 10](#10-el-asistente-interno-sci-ia).
- `clasificar_mensaje(texto)` → `PAGO | CIERRE | OTRO` (una sola llamada barata, temp 0).
- `clasificar_intencion_pago(texto)` → bool (wrapper).
- `extraer_promesa(texto)` → `{monto, fecha_texto, fecha}` con salida **JSON** (calcula la
  fecha relativa desde hoy).

### 8.11 Servicios de canal
- `whatsapp.py` — Cloud API (Graph): `enviar_plantilla` (utility, abre ventana 24h),
  `enviar_texto` (gratis dentro de la ventana). El webhook (`routers/whatsapp.py`) verifica
  el token, procesa estados de entrega y mensajes entrantes (responde con el bot).
- `whatsapp_neonize.py` — WhatsApp Web (ver [sección 9](#9-el-bot-conversacional-de-whatsapp)).
- `twilio_sms.py` — `enviar_sms` (SID de Twilio).
- `vapi.py` — `iniciar_llamada` (assistant + número Vapi, inyecta `nombre`/`monto`/`dni`
  como `variableValues`) y `obtener_llamada(call_id)` (consulta el resultado). El router
  `routers/voice.py` expone `POST /voz/llamar` y `POST /voz/sync` (polling de resultados).

---

## 9. El bot conversacional de WhatsApp

Implementado para el proveedor **neonize** (`services/whatsapp_neonize.py`), que conecta a
WhatsApp Web por un socket persistente (login por QR, sesión local en `sci_wa.db`). No
requiere túnel ni webhook. ⚠️ Es no oficial (riesgo de baneo): solo para pruebas.

### 9.1 Eventos que maneja
| Evento neonize | Acción |
|---|---|
| `QREv` | Imprime el QR en la terminal (segno) para vincular |
| `PairStatusEv` / `ConnectedEv` / `LoggedOutEv` | Log de estado de la sesión |
| `MessageEv` | Mensaje entrante → pipeline del bot |
| `ReceiptEv` | Recibo: DELIVERED → `entregado`, READ/PLAYED → `leido` (avanza el Contacto por id de mensaje) |

### 9.2 Pipeline de un mensaje entrante (`_on_message`)
```
1. Ignora mensajes propios (IsFromMe) y de grupos (IsGroup).
2. Resuelve el número real: WhatsApp puede direccionar por LID (id anónimo); el
   teléfono viene en SenderAlt → _resolver_numero prueba Sender/SenderAlt/Chat y
   se queda con el candidato que matchea un deudor.
3. Gating:
   - Si la conversación está cerrada (_CERRADAS) → ignora.
   - Si el bot no inició la conversación (sin Contacto previo) → ignora, con una
     gracia configurable (WA_GRACIA_SEGUNDOS).
   - No-texto (sticker/imagen) → pide que escriban en texto.
4. _responder_bot:
   - Clasifica el mensaje (PAGO/CIERRE/OTRO).
   - Persiste el mensaje del cliente (Mensaje).
   - Avanza el Contacto (respondido o intencion_pago).
   - Si PAGO: extrae y guarda la Promesa (monto + fecha).
   - Genera la respuesta con memoria (y modo despedida si CIERRE).
   - Persiste la respuesta del bot (Mensaje).
5. Envía la respuesta. Si CIERRE → marca la conversación como cerrada.
```

### 9.3 Reglas de negocio del bot (en el prompt y en el código)
- **Memoria** por número (`_HISTORIAL`, últimos N turnos) → no re-saluda ni pierde hilo.
- **Nombre**: usa solo el del contexto; nunca inventa; saluda una sola vez.
- **Estilo**: 1–3 frases, máx. 1 pregunta por mensaje, foco en la cuota.
- **Cierre**: detecta despedidas, se despide y **deja de responder** a ese número (hasta
  que el bot reinicie una campaña: `enviar_texto` reabre y limpia memoria/cierre).
- **No chats en frío**: solo responde a quien ya contactó.
- **Identificación de teléfono** robusta a `+`, espacios y **LID** (últimos 9 dígitos).

El proveedor **Cloud API** replica clasificación de intención en su webhook; el flujo
completo de captura (memoria/promesas/recibos) vive en el proveedor neonize.

---

## 10. El asistente interno "SCI IA"

Un **analista de cobranza conversacional** para el equipo de cobranzas (no de cara al
cliente deudor), implementado en `routers/assistant.py` + `services/llm.responder_asistente`
+ `components/AsistenteWidget.tsx` (botón flotante en todo el panel).

- `POST /api/assistant/chat` recibe `{mensaje, historial}` (requiere sesión).
- Construye un **snapshot de KPIs en vivo** (`_snapshot`) llamando a
  `analytics.resumen`, `analytics.canales`, `analytics.segmentos` y `orchestrator.plan`, y
  lo inyecta como contexto del system prompt junto con una **guía** (`_GUIA`) que define su
  rol: evaluar estrategias (qué canal por cliente y por qué), leer la evolución de
  resultados y **guiar la navegación** del sistema (mapa de páginas).
- El LLM (mismo cliente que el bot) responde en español de Perú, breve y **apoyado solo en
  los números del snapshot** (no inventa cifras). Si falta la API key, devuelve un mensaje
  claro en vez de 500.

El widget abre un chat con sugerencias ("¿Cómo van los resultados?", "¿Qué canal es más
rentable hoy?", "¿A quién debería priorizar?", "¿Cómo agrego un cliente nuevo?") y mantiene
el historial en el cliente.

---

## 11. Analítica y dashboards

Tres familias claramente separadas en el frontend:

**A. Decisión causal (uplift):**
- **Mapa de persuadibles** (`SegmentosPanel`, de `/analytics/segmentos`): a contactar vs.
  suprimidos (con %), barra de segmentos (persuadible/seguro/perdido/neutro) con clientes,
  monto y uplift medio. Solo aparece si la cartera tiene datos de uplift.

**B. Resultados reales** (de la bitácora `Contacto`/`Mensaje`/`Promesa`):
- **Resumen** (`ResumenRealPanel`): KPIs — contactados, tasa de respuesta, intención (# y
  monto), costo por intención, promesas.
- **Efectividad por canal** (`EfectividadCanalPanel`): embudo + **S/ por conversión** por
  canal, resaltando el más eficiente.
- **GAP por canal** (`GapPanel`): embudo enviado→visto→respondió→intención, con pestañas
  por canal (de `/campaign/metricas`).
- **Cartera** (`CarteraRealPanel`): distribución por riesgo/mora/región/digital + monto en
  riesgo.
- **Priorización** (`PriorizacionPanel`): a quién seguir (intención) y a quién falta
  contactar (alto riesgo).

**C. Proyección** (`ProyeccionPanel`, del orquestador): estimado de costo tradicional vs.
IA, ahorro %, recupero esperado, **anclado a los números reales actuales** para contraste.
Está etiquetado explícitamente como estimación.

---

## 12. Escala y rendimiento (caché, paginación)

Con decenas de miles de clientes, recalcular la analítica (escaneos O(n) en Python) en cada
poll saturaría el backend. Estrategias:

- **Caché en memoria con TTL** (`core/cache.py`): `ttl_cache(key, ttl)` decora los handlers
  de lectura pesados (analítica 8–30 s, plan 30 s, métricas 8 s). La vista es global, así que
  no se cachea por usuario. **`cache.clear()` se llama tras cualquier escritura** (envío,
  ejecución, reset, alta/edición de deudor, importación) para no servir datos viejos.
- **Cache warming** al arrancar (`_warm_cache`, hilo daemon en `main.py`): precalcula todas
  las vistas para que el primer dashboard ya encuentre la caché caliente.
- **Paginación en SQL** (`/strategy/deudores`): filtra y pagina en la base (`offset`/`limit`,
  búsqueda con `ilike`) y solo calcula la recomendación de la página pedida. Devuelve
  `{items, total}`.
- **Listas acotadas**: `/analytics/priorizacion` devuelve el top 100 por monto (la UI lo
  pagina), evitando payloads enormes.
- **Inserción en bloque** en el seed/ETL (`add_all`, sin upsert) para cargar volúmenes
  grandes rápido.

---

## 13. Frontend en detalle

- **Arranque**: `main.tsx` envuelve la app en `BrowserRouter` + `AuthProvider`.
- **Auth** (`auth.tsx`): contexto con `user`, `login`, `logout`. El JWT se guarda en
  `localStorage`; al cargar, `getMe()` revalida. `api.ts` adjunta el Bearer y, ante un
  **401**, limpia el token y redirige a `/login`.
- **Ruteo** (`App.tsx`): `/login` público; el resto bajo `ProtectedRoute` (exige sesión) y
  `Layout`; `/configuracion` además bajo `AdminRoute`. Cualquier ruta desconocida → `/`.
- **Páginas**: Login, Dashboard (uplift + real + proyección), Base de datos (tabla paginada,
  envíos, edición, **alta manual de cliente**, importación XLSX, **Ejecutar estrategias**
  con reporte, reset de actividad), Configuración.
- **Asistente IA** (`AsistenteWidget`): montado en el `Layout`, disponible en todo el panel.
- **Carga del dashboard**: al montar la página (o recargar) hace **una** carga de los datos
  reales + plan + segmentos, y dispara `syncLlamadas()` (Vapi) en segundo plano. **No hace
  polling continuo**: para ver datos nuevos se recarga. Un guard (`cargando`) evita encimar
  ciclos.
- **Estilo**: Tailwind + paleta institucional SCI (`theme.ts`); gráficos con Recharts;
  íconos lucide-react.
- **Proxy dev**: Vite envía `/api` al backend (`localhost:8000`); el health usa
  `http://localhost:8000` directo.

---

## 14. Flujos clave (secuencias)

### 14.1 Login
```
Usuario → POST /api/auth/login (form) → verifica bcrypt → emite JWT
       → frontend guarda token en localStorage → getMe() → set user → /
```

### 14.2 Ejecutar estrategias
```
Admin click "Ejecutar estrategias" → POST /api/campaign/ejecutar {simular}
  → compliance.esta_permitido() (409 si fuera de horario)
  → execution.planificar(): colas + gestión humana + suprimidos + excluidos
       · uplift: 'no_contactar' → suprimido (no se envía nada)
  → asyncio.gather de las 3 colas (cada una secuencial + throttle)
       · simular: registra Contacto "enviado" (detalle "simulado")
       · real:    envía por WhatsApp/SMS/Vapi y registra el resultado
  → cache.clear() → resumen {colas, gestión humana, suprimidos, excluidos}
Frontend muestra el resumen y ofrece descargar el reporte de gestión humana.
```

### 14.3 Conversación de WhatsApp (entrante)
```
Cliente escribe → neonize MessageEv → _on_message
  → resolver número (LID→teléfono) → gating (cerrada / inició / texto)
  → _responder_bot: clasifica → persiste Mensaje → avanza Contacto
       → si PAGO: extrae Promesa → genera respuesta (memoria, cierre)
  → envía respuesta → si CIERRE: cierra conversación
Recibos (entregado/leído) llegan por ReceiptEv y avanzan el Contacto.
```

### 14.4 Resultado de una llamada de Voz (Vapi, sin webhook)
```
Dashboard → POST /api/voz/sync (cada carga)
  → busca Contactos voz_ai recientes que no llegaron a intención
  → vapi.obtener_llamada(call_id) por cada uno
       · status != ended → sigue en curso (no toca)
       · no contestada (endedReason) → se queda en "enviado"
       · contestada → "entregado"; si structuredData.intencion_pago → "intencion_pago"
         (+ crea Promesa con monto_prometido / fecha_compromiso si vienen)
  → cache.clear() implícito en próximas lecturas
```

### 14.5 Preparar la cartera (offline)
```
# Cartera demo (la del proyecto)
python -m scripts.generar_cartera_demo --recargar
  → genera 100 clientes sintéticos con uplift (semilla fija)
  → escribe backend/data/deudores.csv → recarga la base → reinicia el backend

# Cartera real (opcional, requiere las 3 tablas en "datos previos/")
python -m scripts.preparar_datos_reales
  → cruza las 3 tablas y calcula uplift por canal
  → escribe backend/data/clientes_reales.csv → recarga la base → reinicia el backend
```

---

## 15. Configuración (.env)

```ini
ENVIRONMENT=development

# WhatsApp: proveedor
WA_PROVIDER=cloud            # cloud (Meta oficial) | neonize (WhatsApp Web, pruebas)
WA_NEONIZE_SESSION=sci_wa.db
WA_GRACIA_SEGUNDOS=0         # gracia antes de ignorar "sin contacto previo"

# WhatsApp Cloud API (Meta)
WA_ACCESS_TOKEN= · WA_PHONE_NUMBER_ID= · WA_VERIFY_TOKEN= · WA_API_VERSION=v21.0

# Twilio (SMS)
TWILIO_ACCOUNT_SID= · TWILIO_AUTH_TOKEN= · TWILIO_SMS_FROM=

# Vapi (Voz IA)
VAPI_API_KEY= · VAPI_ASSISTANT_ID= · VAPI_PHONE_NUMBER_ID=

# LLM (bot + asistente) — proveedor configurable
LLM_PROVIDER=gemini          # gemini (gratis) | groq (gratis) | openai
LLM_API_KEY= · LLM_MODEL=gemini-2.5-flash · LLM_BASE_URL=
OPENAI_API_KEY= · OPENAI_MODEL=gpt-4o-mini   # fallback / proveedor openai

# Cumplimiento (Indecopi)
COMPLIANCE_ENABLED=true · COMPLIANCE_HORA_INICIO=7 · COMPLIANCE_HORA_FIN=20

# Auth / BD
JWT_SECRET= · JWT_ALGORITHM=HS256 · JWT_EXPIRE_MINUTES=480
DATABASE_URL=sqlite:///./sci.db
```

> `.env` está en `.gitignore` (junto con `sci_wa*` de la sesión de WhatsApp, `*.db`, la
> carpeta `datos previos/` y `backend/data/clientes_reales.csv`). `.env.example` se versiona
> con placeholders: **nunca** pongas secretos ahí.

---

## 16. Seguridad, privacidad y cumplimiento

- **Acceso**: la app siempre entra por `/login`; rutas protegidas por JWT y rol. Las
  credenciales demo no se muestran en la UI (solo en el README).
- **Secretos**: solo en `backend/.env` (gitignoreado). La sesión de neonize contiene
  credenciales de WhatsApp → también gitignoreada (`sci_wa*`).
- **Datos**: el repositorio solo contiene la **cartera demo sintética** (100 clientes
  inventados). Cualquier cartera real —las 3 tablas en `datos previos/` y el
  `clientes_reales.csv` derivado— está gitignoreada (pesada y confidencial).
- **Indecopi (Art. 62b)**: ventana de contacto 07:00–20:00, sin domingos/feriados.
- **Ley 29733 (datos personales)**: el `Deudor` registra `consentimiento` y `opt_out`; los
  excluidos no se contactan. La supresión por uplift también reduce contactos innecesarios.
  Disclosure de "llamada grabada" y validación de DNI del titular en el prompt de Voz.
- **No revelar la deuda a terceros** ni lenguaje intimidatorio (reglas en el prompt).
- ⚠️ El proveedor **neonize es no oficial** (contra los Términos de Meta): solo pruebas con
  un número descartable. Producción → Cloud API oficial.

---

## 17. Decisiones de diseño y limitaciones

**Decisiones**
- **Uplift sobre scoring**: se decide por incrementalidad (a quién mueve el contacto), con
  supresión de quien no aporta valor incremental. La escalera de costo es el **respaldo**
  cuando faltan datos de uplift → el sistema siempre decide algo sensato.
- **Una sola puerta de decisión** (`asignar_canal`): uplift o reglas según `tiene_uplift`,
  para que routers y dashboards no dupliquen lógica.
- **`intencion_pago` como métrica de resultado**: el pago real no se confirma
  automáticamente (sería integración bancaria), así que la intención —detectada por el bot
  o por el análisis de la llamada— es la mejor señal real y guía los KPIs.
- **Datos reales vs. proyección separados** en la UI para no confundir estimación con hecho.
- **Lógica pura en `core/`** (uplift, asignación, embudo, planificación) → testeable sin I/O.
- **Caché + paginación** para operar a escala sin sacar SQLite de su zona cómoda.

**Limitaciones conocidas (MVP)**
- **SQLite** monoinstancia (suficiente para el MVP; producción → Postgres).
- **Memoria de conversación, cierres y caché en RAM**: se limpian al reiniciar el backend.
- **neonize requiere arrancar sin `--reload`** (el reload rompe la sesión de WhatsApp).
- **Embudo por canal**: WhatsApp tiene embudo completo (bot + recibos); **Voz** avanza vía
  polling a Vapi (`/voz/sync`: contestada→entregado, intención→intencion_pago + promesa);
  **SMS** se queda en "enviado" (no hay webhooks de estado de Twilio conectados).
- **Uplift**: estimado del dataset (post − base). Para producción, recalibrar con A/B
  (grupo de control sin contacto) y validar fatiga/umbral de supresión.
- **Promesas**: la fecha se interpreta con el LLM (relativa a hoy); validar antes de operar.

**Extensiones naturales**
- Webhooks de estado de Twilio para completar el embudo de SMS.
- Confirmación de pago real (conciliación) para cerrar el ciclo recupero y medir el uplift
  observado vs. estimado.
- Persistir memoria/cierres y promesas con seguimiento (recordatorios automáticos vía
  `scheduler`).
- Calibración online del uplift y del umbral de supresión por segmento.
- Análisis de conversaciones (objeciones, motivos de no pago, sentimiento) sobre `Mensaje`.
