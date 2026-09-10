// Colorimetría institucional SCI (compartida por la UI y los charts de Recharts).
export const SCI = {
  verde: "#00964B",
  verdeOscuro: "#007539",
  amarillo: "#FFD100",
  oro: "#FAB500",
  naranja: "#F28F00",
  gris: "#6B7280",
  rojo: "#DC2626",
  azul: "#0EA5E9",
};

// Color de cada canal en gráficos.
export const COLOR_CANAL: Record<string, string> = {
  whatsapp: SCI.verde,
  sms: SCI.oro,
  voz_ai: SCI.naranja,
  llamada_humana: SCI.gris,
  visita: SCI.rojo,
  ninguno: "#CBD5E1",
};

// Orden y nombre legible de cada canal.
export const CANALES_ORDEN = ["whatsapp", "sms", "voz_ai", "llamada_humana", "visita"];
export const NOMBRE_CANAL: Record<string, string> = {
  whatsapp: "WhatsApp",
  sms: "SMS",
  voz_ai: "Voz AI",
  llamada_humana: "Llamada humana",
  visita: "Visita de campo",
};

// Clases Tailwind para los badges de canal.
export const BADGE_CANAL: Record<string, string> = {
  whatsapp: "bg-green-100 text-green-800",
  sms: "bg-yellow-100 text-yellow-800",
  voz_ai: "bg-orange-100 text-orange-800",
  llamada_humana: "bg-slate-200 text-slate-700",
  visita: "bg-red-100 text-red-700",
  ninguno: "bg-slate-100 text-slate-500",
};
