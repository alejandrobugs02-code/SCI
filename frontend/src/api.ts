import axios from "axios";

// En dev, Vite hace proxy de /api -> http://localhost:8000 (ver vite.config.ts).
const api = axios.create({ baseURL: "/api" });
// El health vive en la raíz del backend, fuera del prefijo /api.
const root = axios.create({ baseURL: "http://localhost:8000" });

// Adjunta/limpia el token JWT en ambas instancias.
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
    root.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
    delete root.defaults.headers.common.Authorization;
  }
}

// Si el token expira/invalida, vuelve al login.
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      setAuthToken(null);
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ---------- Tipos ----------
export interface CanalConfig {
  nombre: string;
  costo: number;
  tasa_pago: number;
  contactabilidad: number;
  categoria: string;
  orden: number;
}

export interface Recomendacion {
  canal: string;
  nombre: string;
  categoria: string;
  costo: number;
  valor_esperado: number;
  motivo: string;
  accion?: "contactar" | "no_contactar";
  uplift?: number;
  segmento?: string;
}

export interface Deudor {
  id: number;
  cliente_id: string;
  nombre: string;
  telefono: string;
  documento: string;
  monto_deuda: number;
  edad: number;
  genero: string;
  region: string;
  zona: string;
  tipo_cliente: string;
  es_digital: boolean;
  uso_app: number;
  uso_whatsapp: number;
  interaccion_digital_score: number;
  canal_whatsapp: boolean;
  canal_sms: boolean;
  canal_llamada: boolean;
  canal_campo: boolean;
  score_riesgo: number;
  prob_default: number;
  num_atrasos_previos: number;
  dias_mora_promedio: number;
  ratio_pago: number;
  ultimo_pago_dias: number;
  dias_mora: number;
  riesgo: string;
  opt_out: boolean;
  consentimiento: boolean;
  recomendacion: Recomendacion;
}

export interface CanalPlan {
  nombre: string;
  categoria: string;
  deudores: number;
  monto: number;
  costo: number;
}

export interface Plan {
  deudores_gestionados: number;
  suprimidos?: number;
  excluidos_opt_out: number;
  deuda_total: number;
  costo_optimizado: number;
  costo_baseline: number;
  ahorro_soles: number;
  ahorro_pct: number;
  recupero_esperado: number;
  por_canal: Record<string, CanalPlan>;
  proyeccion_gap: {
    contactabilidad_pct: number;
    promesas_pago_pct: number;
    gap_pct: number;
  };
}

export interface Health {
  app: string;
  status: string;
  ventana_contacto: { permitido: boolean; motivo: string };
}

export interface Usuario {
  username: string;
  nombre: string;
  rol: string;
}

export interface LoginResp extends Usuario {
  access_token: string;
  token_type: string;
}

export interface AppConfig {
  id: number;
  prompt_whatsapp: string;
  prompt_voz: string;
  dias_temprana: number;
  dias_media: number;
  dias_tardia: number;
  monto_riesgo_temprano: number;
  monto_voz_humano: number;
  monto_visita: number;
  canales: Record<string, CanalConfig>;
}

export interface Embudo {
  enviados: number;
  entregados: number;
  vistos: number;
  respondidos: number;
  intencion: number;
  pagados: number;
  monto_intencion: number;
  tasas: {
    entrega: number;
    apertura: number;
    respuesta: number;
    intencion: number;
    pago: number;
  };
}

export interface CampaignMetricas {
  campania_iniciada: boolean;
  enviados: number;
  vistos: number;
  respondidos: number;
  intencion: number;
  pagados: number;
  costo_acumulado: number;
  monto_recuperado: number;
  tasas: Embudo["tasas"];
  embudo: Embudo;
  embudo_por_canal: Record<string, Embudo>;
  gasto_por_mes: { mes: string; costo: number }[];
  por_canal: Record<string, { enviados: number; costo: number }>;
}

// Cada fila trae monto por canal (clave = canal) + nº (clave canal_n).
export type CarteraRow = {
  tramo: string;
  deudores: number;
  monto: number;
} & Record<string, number>;

// ---------- Auth ----------
export const login = (username: string, password: string) => {
  const form = new URLSearchParams();
  form.append("username", username);
  form.append("password", password);
  return api.post<LoginResp>("/auth/login", form).then((r) => r.data);
};

export const getMe = () => api.get<Usuario>("/auth/me").then((r) => r.data);

// ---------- Datos ----------
export const getCanales = () =>
  api.get<Record<string, CanalConfig>>("/strategy/canales").then((r) => r.data);

export interface DeudoresPagina {
  items: Deudor[];
  total: number;
}

export const getDeudores = (q = "", offset = 0, limit = 50) =>
  api
    .get<DeudoresPagina>("/strategy/deudores", { params: { q, offset, limit } })
    .then((r) => r.data);

export const getPlan = () => api.get<Plan>("/orchestrator/plan").then((r) => r.data);

export const getHealth = () => root.get<Health>("/").then((r) => r.data);

// ---------- Configuración (admin) ----------
export const getConfig = () => api.get<AppConfig>("/config").then((r) => r.data);

export const putConfig = (body: Record<string, unknown>) =>
  api.put<AppConfig>("/config", body).then((r) => r.data);

// ---------- Cartera ----------
export const getCartera = () =>
  api.get<CarteraRow[]>("/strategy/cartera").then((r) => r.data);

// ---------- Campaña ----------
export const getMetricas = () =>
  api.get<CampaignMetricas>("/campaign/metricas").then((r) => r.data);

export const enviarCampania = (deudor_id: number, canal: string) =>
  api.post("/campaign/enviar", { deudor_id, canal }).then((r) => r.data);

// Reinicia la actividad (contactos/mensajes/promesas); conserva los clientes. (admin)
export const resetDatos = () =>
  api
    .post<{ status: string; borrados: Record<string, number> }>("/campaign/reset")
    .then((r) => r.data);

// Trae de Vapi el resultado de las llamadas recientes (contestada / intención de pago).
export const syncLlamadas = () =>
  api.post<{ revisados: number; actualizados: number }>("/voz/sync").then((r) => r.data);

// ---------- Ejecución automatizada de estrategias (admin) ----------
export interface EjecucionResumen {
  simulado: boolean;
  contactos_registrados: number;
  colas: Record<string, { total: number; enviados: number; fallidos: number }>;
  gestion_humana: { total: number; por_canal: Record<string, number> };
  suprimidos: number;
  excluidos: number;
}

export const ejecutarEstrategias = (simular: boolean) =>
  api.post<EjecucionResumen>("/campaign/ejecutar", { simular }).then((r) => r.data);

// Descarga el CSV de clientes que requieren llamada humana o visita de campo.
export const descargarReporteGestionHumana = async () => {
  const r = await api.get("/campaign/reporte-gestion-humana", { responseType: "blob" });
  const url = URL.createObjectURL(r.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "reporte_gestion_humana.csv";
  a.click();
  URL.revokeObjectURL(url);
};

// ---------- Analítica (datos reales) ----------
export interface AnalyticsResumen {
  tiene_datos: boolean;
  deudores_total: number;
  deuda_total: number;
  contactados: number;
  respondidos: number;
  intencion: number;
  tasa_respuesta: number;
  tasa_intencion: number;
  monto_intencion: number;
  costo_real: number;
  costo_por_intencion: number;
  promesas: number;
  monto_prometido: number;
}

export interface CanalEfectividad {
  nombre: string;
  enviados: number;
  entregados: number;
  vistos: number;
  respondidos: number;
  intencion: number;
  costo: number;
  costo_por_intencion: number;
  tasa_lectura: number;
  tasa_respuesta: number;
  tasa_intencion: number;
}

export interface Grupo {
  deudores: number;
  monto: number;
}

export interface AnalyticsCartera {
  deudores_total: number;
  deuda_total: number;
  monto_en_riesgo: number;
  por_riesgo: Record<string, Grupo>;
  por_tramo_mora: Record<string, Grupo>;
  por_region: Record<string, Grupo>;
  digital: Record<string, Grupo>;
}

export interface DeudorPrioridad {
  cliente_id: string;
  nombre: string;
  telefono: string;
  monto_deuda: number;
  riesgo: string;
  dias_mora?: number;
  promesa_monto?: number | null;
  promesa_fecha_texto?: string;
  promesa_fecha?: string | null;
}

export interface AnalyticsPriorizacion {
  con_intencion: DeudorPrioridad[];
  alto_riesgo_sin_contactar: DeudorPrioridad[];
}

export const getAnalyticsResumen = () =>
  api.get<AnalyticsResumen>("/analytics/resumen").then((r) => r.data);

// ---------- Segmentación causal (uplift) ----------
export interface SegmentoUplift {
  label: string;
  clientes: number;
  monto: number;
  uplift_medio: number;
}

export interface AnalyticsSegmentos {
  tiene_uplift: boolean;
  segmentos?: SegmentoUplift[];
  total?: number;
  persuadibles?: number;
  persuadibles_pct?: number;
  escalados_campo?: number;
  por_canal_recomendado?: Record<string, number>;
  costo_optimizado?: number;
}

export const getAnalyticsSegmentos = () =>
  api.get<AnalyticsSegmentos>("/analytics/segmentos").then((r) => r.data);

// ---------- Asistente IA del panel ----------
export interface ChatTurno {
  role: "user" | "assistant";
  content: string;
}

export const chatAsistente = (mensaje: string, historial: ChatTurno[]) =>
  api
    .post<{ respuesta: string }>("/assistant/chat", { mensaje, historial })
    .then((r) => r.data.respuesta);

export const getAnalyticsCanales = () =>
  api.get<Record<string, CanalEfectividad>>("/analytics/canales").then((r) => r.data);
export const getAnalyticsCartera = () =>
  api.get<AnalyticsCartera>("/analytics/cartera").then((r) => r.data);
export const getAnalyticsPriorizacion = () =>
  api.get<AnalyticsPriorizacion>("/analytics/priorizacion").then((r) => r.data);

// ---------- Deudores (admin) ----------
export interface DeudorNuevo {
  nombre: string;
  telefono?: string;
  documento?: string;
  monto_deuda?: number;
  dias_mora?: number;
  riesgo?: string;          // bajo · medio · alto
  region?: string;
  cliente_id?: string;      // opcional; se autogenera si va vacío
}

export const crearDeudor = (body: DeudorNuevo) =>
  api.post<Deudor>("/deudores", body).then((r) => r.data);

export const updateDeudor = (id: number, body: Partial<Deudor>) =>
  api.put<Deudor>(`/deudores/${id}`, body).then((r) => r.data);

export const importarDeudores = (file: File, reemplazar = false) => {
  const fd = new FormData();
  fd.append("archivo", file);
  return api
    .post(`/deudores/importar?reemplazar=${reemplazar}`, fd)
    .then((r) => r.data);
};
