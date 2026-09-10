# Estrategia técnica — Cómo SCI reduce el costo de cobranza sin perder recupero

*Pitch de negocio de SCI — Sistema de Cobranzas Inteligente.*

---

## 1. El problema y dónde está la plata

En cobranza hay **dos formas de quemar plata**, y la segunda es la que casi nadie
mide:

1. **Usar el canal caro donde bastaba el barato.** La mora temprana (0–30 días)
   es masiva en volumen pero de bajo riesgo: la mayoría solo necesita un
   recordatorio. El modelo tradicional la trabaja con **contact center humano
   (S/1.50)** e incluso **visita de campo (S/8.00)**.
2. **Tratar igual a todos los morosos.** A quien iba a pagar solo le basta un
   recordatorio barato; a quien no reacciona a nada hay que escalarlo a un canal
   intensivo. Usar el mismo canal —caro o barato— para ambos desperdicia plata o
   pierde recupero.

La cobranza clásica optimiza *"¿quién va a pagar?"* (un modelo de scoring). La
pregunta de negocio más útil es **causal**:

> **¿Qué canal hace pagar a cada cliente — y a quién no lo mueve ningún canal barato?**

El banco gestiona a **todos** los morosos (no deja a nadie sin contactar), así que
la palanca de ahorro es **el canal**: mover la mora temprana y a los "persuadibles"
a canales digitales baratos, y reservar lo caro (humano, **visita de campo**) para
quienes ningún canal barato mueve.

---

## 2. La solución: orquestación por incrementalidad (uplift)

SCI decide cada contacto con un motor de **uplift / incrementalidad**
(`backend/app/core/uplift.py`). Para cada cliente y canal estima el **uplift**:

```
uplift_canal = P(paga en 7 días | lo contacto por ese canal)
             − P(paga en 7 días | no lo contacto)
```

y elige la acción que **maximiza el pago incremental**, descontando costo y
fatiga (anti-sobregestión):

```
valor_incremental(canal) = uplift_canal × monto_recuperable
                           − costo_canal − λ · contactos_recientes
```

- **Si algún canal aporta valor incremental positivo** → se gestiona por ese canal
  (el que más mueve el pago, no el más barato a secas).
- **Si ningún canal aporta valor incremental** (el cliente pagaría solo o no
  reacciona) → **gestión total**: el banco no deja a nadie sin contactar, así que
  se re-evalúa por la **escalera de mora** y se escala a **visita de campo** cuando
  no hay otra forma. Lo caro queda reservado para estos casos duros, no se gasta a
  ciegas en toda la cartera.

### Segmentación causal de la cartera
El mismo motor clasifica a cada cliente y lo hace visible en el dashboard
("Mapa de persuadibles") — la acción es **gestionar a todos**, variando el canal:

| Segmento | Qué es | Acción (gestión total) |
|---|---|---|
| **Persuadible** | el contacto sí mueve su pago (uplift alto) | gestionar por su **mejor canal** (el de mayor pago incremental) |
| **Seguro** | paga prácticamente solo (prob. base alta) | gestionar por el **canal más barato** (recordatorio) |
| **Perdido** | no reacciona ni con contacto (prob. base baja) | **escalar a visita de campo** (último recurso) |
| **Neutro / dudoso** | sin señal clara | gestionar por la **escalera de mora** |

### Capa de respaldo: escalera de costo (next-best-action)
Cuando un cliente **no tiene datos de uplift** (alta manual, importación sin esas
columnas, cartera sin tabla de contactos), el orquestador cae automáticamente a la
**escalera de costo creciente** por mora × monto × riesgo, respetando la
disponibilidad de canal de cada cliente:

| Tramo | Canal asignado | Por qué |
|---|---|---|
| Día 0 / por vencer | **SMS** preventivo | Recordatorio unidireccional, costo mínimo |
| 1–30 días | **WhatsApp** (agente IA) | Gestión interactiva barata, alta tasa de pago |
| 1–30 sin WhatsApp | **SMS** | Fallback cuando no hay canal digital interactivo |
| 1–30 alto riesgo + monto alto | **Voz AI** | Refuerzo persuasivo temprano |
| 31–60 días | **Voz AI** / humano (si monto alto) | Toque de voz a fracción del costo humano |
| 61–90 días | **Llamada humana** | Negociación de plan de pago |
| >90 días y monto alto | **Visita de campo** | Último recurso, solo cuando el valor lo justifica |

Así el sistema **siempre** decide algo sensato: con datos reales optimiza por
incrementalidad; sin ellos, por la escalera de costo. Una sola función
(`orchestrator.asignar_canal`) elige la capa según `tiene_uplift`.

Los agentes de WhatsApp y Voz usan un **system prompt con el tono SCI**
(empático, lenguaje simple, sin negativas categóricas, máx. 2 emojis), para que
la reducción de costo **no sacrifique la experiencia del cliente**.

---

## 3. El dato que lo sostiene

El motor necesita, por cliente y canal: `prob_pago_base` (probabilidad de pago a 7
días sin contacto), `uplift_{whatsapp,sms,llamada,campo}`, `cuota_mensual` (monto
recuperable en la ventana) y `num_contactos_ult7d` (fatiga). SCI los obtiene por
dos vías:

**a) Cartera demo (la que trae el proyecto).**
`backend/scripts/generar_cartera_demo.py` genera 100 clientes **sintéticos** con
todos esos campos, calibrados para reproducir una cartera realista: mora repartida
en los cinco tramos, riesgo correlacionado con la mora, disponibilidad de canal
ligada al perfil digital y los cuatro segmentos causales (≈42 persuadibles, 20
seguros, 13 perdidos, 21 neutros). Semilla fija → reproducible.

**b) Cartera real (opcional).**
`backend/scripts/preparar_datos_reales.py` cruza tres tablas de origen y calcula
el uplift observado:

```
Tabla de clientes  → features demográficas, riesgo, disponibilidad de canal
Tabla de créditos  → saldo, cuota, mora real, prob_pago_7d_base
Tabla de contactos → prob_pago_7d_post por canal  ⇒  uplift, fatiga, costo
```

Escribe `clientes_reales.csv`, que el backend prefiere al arrancar si existe.

---

## 4. La prueba: de dónde sale el ahorro

El endpoint `/api/orchestrator/plan` compara, sobre la **misma cartera** y
gestionando a **todos** los no excluidos, el **modelo tradicional** (contact
center humano para mora ≤90 días + visita para >90 con monto alto) contra la
**orquestación de SCI**. El ahorro viene de la **sustitución de canal**:

- Cada cuenta de mora temprana o "persuadible" movida de **S/1.50 → S/0.10**
  (humano → WhatsApp) ahorra **S/1.40**.
- La **Voz AI** absorbe el tramo medio a **~1/2 del costo humano con capacidad
  ilimitada en paralelo** (miles de llamadas simultáneas sin contratar agentes).
- La **visita de campo** (S/8.00), el recurso más caro, se reserva **solo** para
  los casos donde ningún canal barato mueve el pago, en vez de aplicarse a ciegas.

El uplift no decide *si* contactar (el banco gestiona a todos) sino **cómo**:
prioriza y elige el canal que más mueve el pago de cada cliente.

> **Por qué escala:** la palanca es estructural y multiplicativa. En una cartera
> real de cientos de miles de cuentas, digitalizar la mora temprana y a los
> persuadibles, y reservar lo caro para lo que de verdad lo necesita, mueve el
> costo total de cobranza muy por encima de la meta del 10% — **sin bajar el
> recupero**, porque la mora temprana se atiende con canales de **mayor** tasa de
> pago (WhatsApp 53.5% vs. llamada humana 47%).

*(Sobre la cartera demo de 100 clientes con uplift: **S/189.50** de costo
tradicional → **S/76.00** con SCI, **−59.9%**, gestionando a los mismos 96 clientes
no excluidos. El número se recalcula en vivo en el dashboard según la cartera y los
parámetros de canal; no está hardcodeado.)*

---

## 5. Diferenciadores que protegen el ahorro

- **Decisión causal, no solo predictiva:** SCI no pregunta "¿quién paga?" sino
  "¿a quién mueve el contacto?". Eso elimina el gasto invisible en seguros y
  perdidos que ningún scoring tradicional recorta.
- **Cumplimiento por diseño (no como parche):** validador Indecopi que bloquea
  envíos fuera de 07:00–20:00 (L–S) y en feriados peruanos (`core/compliance.py`),
  + gestión de consentimiento/opt-out (Ley 29733). Evita multas que borrarían
  cualquier ahorro.
- **Experiencia de cliente cuidada:** agentes con tono SCI → menor fricción,
  mayor tasa de promesa de pago. La supresión también es CX: deja de molestar a
  quien no hace falta contactar.
- **Asistente analista interno ("SCI IA"):** un chat en el panel que lee los
  KPIs reales en vivo (embudo, costo por intención, ahorro, segmentos) y responde
  preguntas del equipo y guía la operación.
- **Observabilidad financiera (rol Visor):** costo real por canal, **costo por
  intención de pago**, **GAP** de eficiencia (contactabilidad ↔ promesas) y monto
  en riesgo, en tiempo real.

---

## 6. Cómo lo demostramos en vivo

1. **Dashboard** (rol **Super Administrador**): KPIs reales de la campaña, **Mapa
   de persuadibles** (a contactar vs. suprimidos), efectividad y costo por canal,
   GAP, cartera y panel de **ahorro vs. modelo tradicional**.
2. **Ejecutar estrategias** sobre la cartera: el orquestador reparte en colas
   (WhatsApp/SMS/Voz AI), reporta gestión humana y **cuenta los suprimidos**.
3. **Asistente "SCI IA":** preguntar en lenguaje natural "¿a quién priorizo?",
   "¿qué canal rinde más?" y ver que responde con los números del panel.
4. **Validador Indecopi** en vivo (la franja superior cambia según el horario).
5. Cambio a rol **Visor**: mismos dashboards en modo lectura.
6. Mensaje real por WhatsApp/SMS y una llamada de Voz AI de prueba.

---

## 7. Supuestos y transparencia

- La **cartera del demo es sintética** (100 clientes generados, ningún dato real).
  Está calibrada para reproducir una distribución realista, pero las cifras que
  muestra el panel son ilustrativas hasta cargar una cartera de verdad.
- El **uplift** se estima de la tabla de contactos (prob. de pago post-contacto
  por canal − base). Es un estimado del dataset; en producción se recalibra con
  experimentos A/B (grupo de control sin contacto).
- Costos y tasas de pago por canal son inputs editables (`core/nba.py` y la
  página de Configuración); la tasa y contactabilidad de **Voz AI son estimadas**
  (a validar en piloto).
- El "modelo tradicional" de comparación asume contact center humano para mora
  ≤90 días y visita para >90 con monto alto — el patrón pre-digital típico.
- Ajustando estos parámetros, el cálculo de ahorro **se recalcula
  automáticamente** y se refleja en el dashboard.

> 📐 Detalle técnico completo (motor de uplift, caché, escala, asistente):
> ver [ARQUITECTURA.md](ARQUITECTURA.md). Puesta en marcha: [README.md](README.md).
