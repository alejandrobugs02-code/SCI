import { MapPin, Sparkles, Target } from "lucide-react";
import type { AnalyticsSegmentos } from "../api";
import { soles } from "../format";

// Color por segmento (orden: persuadible, seguro, perdido, neutro).
const COLOR = ["#00964B", "#0EA5E9", "#9CA3AF", "#F28F00"];

export default function SegmentosPanel({ data }: { data: AnalyticsSegmentos }) {
  if (!data.tiene_uplift || !data.segmentos) return null;
  const total = data.segmentos.reduce((s, x) => s + x.clientes, 0) || 1;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-1 flex items-center gap-2">
        <Sparkles size={18} className="text-sci-verde" />
        <h2 className="text-base font-semibold text-slate-800">Mapa de persuadibles</h2>
        <span className="text-xs font-normal text-slate-400">· incrementalidad (uplift)</span>
      </div>
      <p className="mb-4 text-xs text-slate-500">
        Priorizamos por cuánto <strong>mueve</strong> el contacto el pago. Se gestiona a todos:
        a los persuadibles por su mejor canal y, cuando ningún canal aporta, se escala a
        <strong> visita de campo</strong>.
      </p>

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-sci-verde/10 p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-sci-verde-oscuro">
            <Target size={15} /> Persuadibles
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-800">{data.persuadibles}</div>
          <div className="text-xs text-slate-500">
            {data.persuadibles_pct}% — el contacto mueve su pago
          </div>
        </div>
        <div className="rounded-xl bg-amber-50 p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-amber-700">
            <MapPin size={15} /> Escalados a campo
          </div>
          <div className="mt-1 text-2xl font-bold text-slate-800">{data.escalados_campo}</div>
          <div className="text-xs text-slate-500">visita: sin otra forma de gestión</div>
        </div>
      </div>

      {/* Barra de distribución de segmentos */}
      <div className="mb-2 flex h-3 w-full overflow-hidden rounded-full">
        {data.segmentos.map((s, i) => (
          <div
            key={s.label}
            style={{ width: `${(s.clientes / total) * 100}%`, background: COLOR[i] }}
            title={`${s.label}: ${s.clientes}`}
          />
        ))}
      </div>

      <div className="space-y-1.5">
        {data.segmentos.map((s, i) => (
          <div key={s.label} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-slate-600">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLOR[i] }} />
              {s.label}
            </span>
            <span className="text-slate-500">
              {s.clientes.toLocaleString()} · {soles(s.monto)} ·{" "}
              <span className="text-slate-400">uplift {s.uplift_medio >= 0 ? "+" : ""}{s.uplift_medio}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
