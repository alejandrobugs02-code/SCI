import { useState } from "react";
import {
  CheckCircle2,
  Eye,
  HandCoins,
  MessageSquare,
  Phone,
  PhoneCall,
  Send,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { CampaignMetricas, Embudo } from "../api";
import { soles2 } from "../format";
import { SCI, NOMBRE_CANAL } from "../theme";

function Paso({
  icon: Icon,
  label,
  valor,
  pct,
  color,
}: {
  icon: LucideIcon;
  label: string;
  valor: number;
  pct?: number;
  color: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 text-slate-600">
          <Icon size={15} /> {label}
        </span>
        <span className="font-semibold text-slate-800">
          {valor}
          {pct !== undefined && <span className="ml-1 text-xs text-slate-400">({pct}%)</span>}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full" style={{ width: `${pct ?? 100}%`, background: color }} />
      </div>
    </div>
  );
}

// Cada canal muestra su propio embudo, con las etiquetas propias del medio
// (una llamada se "contesta", un SMS "llega"). Si un canal no está aquí, usa
// el embudo genérico de mensajería (PASOS_DEFAULT).
type PasoDef = {
  icon: LucideIcon;
  label: string;
  valor: (e: Embudo) => number;
  pct?: (e: Embudo) => number;
  color: string;
};

const PASOS_DEFAULT: PasoDef[] = [
  { icon: Send, label: "Enviados", valor: (e) => e.enviados, color: SCI.gris },
  { icon: Eye, label: "Vieron el mensaje", valor: (e) => e.vistos, pct: (e) => e.tasas.apertura, color: SCI.oro },
  { icon: MessageSquare, label: "Respondieron", valor: (e) => e.respondidos, pct: (e) => e.tasas.respuesta, color: SCI.naranja },
  { icon: HandCoins, label: "Intención de pago", valor: (e) => e.intencion, pct: (e) => e.tasas.intencion, color: SCI.verde },
];

const PASOS_POR_CANAL: Record<string, PasoDef[]> = {
  voz_ai: [
    { icon: Phone, label: "Llamadas enviadas", valor: (e) => e.enviados, color: SCI.gris },
    { icon: PhoneCall, label: "Llamadas contestadas", valor: (e) => e.entregados, pct: (e) => e.tasas.entrega, color: SCI.oro },
    { icon: HandCoins, label: "Intención de pago", valor: (e) => e.intencion, pct: (e) => e.tasas.intencion, color: SCI.verde },
  ],
  sms: [
    { icon: Send, label: "Enviados", valor: (e) => e.enviados, color: SCI.gris },
    { icon: CheckCircle2, label: "Llegados correctamente", valor: (e) => e.entregados, pct: (e) => e.tasas.entrega, color: SCI.verde },
  ],
};

// Orden preferido de pestañas (WhatsApp primero: es el canal con más señal).
const ORDEN = ["whatsapp", "voz_ai", "sms"];

export default function GapPanel({ metricas }: { metricas: CampaignMetricas }) {
  const canales = Object.keys(metricas.embudo_por_canal ?? {}).sort(
    (a, b) => (ORDEN.indexOf(a) + 1 || 99) - (ORDEN.indexOf(b) + 1 || 99)
  );
  const [canal, setCanal] = useState<string>(canales[0] ?? "whatsapp");

  if (!metricas.campania_iniciada || canales.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-800">GAP de eficiencia (en vivo)</h2>
        <div className="mt-3 flex h-[200px] items-center justify-center rounded-lg bg-slate-50 text-center text-xs text-slate-400">
          La campaña aún no inicia.<br />Envía mensajes desde Base de datos para medir
          contactabilidad, respuestas e intención de pago.
        </div>
      </div>
    );
  }

  const activo = canales.includes(canal) ? canal : canales[0];
  const e: Embudo = metricas.embudo_por_canal[activo];
  const pasos = PASOS_POR_CANAL[activo] ?? PASOS_DEFAULT;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-800">GAP de eficiencia (en vivo)</h2>
        <span className="rounded-full bg-sci-verde/10 px-2 py-0.5 text-xs font-medium text-sci-verde-oscuro">
          campaña activa
        </span>
      </div>

      {/* Pestañas por canal */}
      <div className="mt-3 flex gap-1.5">
        {canales.map((c) => (
          <button
            key={c}
            onClick={() => setCanal(c)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              c === activo
                ? "bg-sci-verde text-white"
                : "bg-slate-100 text-slate-500 hover:bg-slate-200"
            }`}
          >
            {NOMBRE_CANAL[c] ?? c}
          </button>
        ))}
      </div>

      <p className="mb-4 mt-3 text-xs text-slate-400">
        Embudo de {NOMBRE_CANAL[activo] ?? activo}: del envío hasta la intención de pago.
      </p>

      <div className="space-y-3">
        {pasos.map((p) => (
          <Paso key={p.label} icon={p.icon} label={p.label} valor={p.valor(e)} pct={p.pct?.(e)} color={p.color} />
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-sm">
        <span className="flex items-center gap-2 text-slate-500">
          <CheckCircle2 size={15} className="text-sci-verde" /> Monto en intención de pago
        </span>
        <span className="font-semibold text-sci-verde">{soles2(e.monto_intencion)}</span>
      </div>
    </div>
  );
}
