import type { CanalEfectividad } from "../api";
import { soles2 } from "../format";
import { BADGE_CANAL, CANALES_ORDEN, SCI } from "../theme";

// Cada canal muestra su propio embudo, con las etapas y etiquetas propias del
// medio (una llamada se "contesta", un SMS "llega", un WhatsApp se "lee").
type Etapa = { label: string; valor: (c: CanalEfectividad) => number; color: string };

const ETAPAS_DEFAULT: Etapa[] = [
  { label: "Enviados", valor: (c) => c.enviados, color: SCI.gris },
  { label: "Leídos", valor: (c) => c.vistos, color: SCI.oro },
  { label: "Respondió", valor: (c) => c.respondidos, color: SCI.naranja },
  { label: "Intención", valor: (c) => c.intencion, color: SCI.verde },
];

const ETAPAS_POR_CANAL: Record<string, Etapa[]> = {
  voz_ai: [
    { label: "Enviadas", valor: (c) => c.enviados, color: SCI.gris },
    { label: "Contestadas", valor: (c) => c.entregados, color: SCI.oro },
    { label: "Intención", valor: (c) => c.intencion, color: SCI.verde },
  ],
  sms: [
    { label: "Enviados", valor: (c) => c.enviados, color: SCI.gris },
    { label: "Llegados", valor: (c) => c.entregados, color: SCI.oro },
    { label: "Intención", valor: (c) => c.intencion, color: SCI.verde },
  ],
  whatsapp: [
    { label: "Enviados", valor: (c) => c.enviados, color: SCI.gris },
    { label: "Leídos", valor: (c) => c.vistos, color: SCI.oro },
    { label: "Respondió", valor: (c) => c.respondidos, color: SCI.naranja },
    { label: "Intención", valor: (c) => c.intencion, color: SCI.verde },
  ],
};

function pct(valor: number, base: number) {
  return base ? Math.round((valor / base) * 100) : 0;
}

function TarjetaCanal({ canal, c, mejor }: { canal: string; c: CanalEfectividad; mejor: boolean }) {
  const etapas = ETAPAS_POR_CANAL[canal] ?? ETAPAS_DEFAULT;
  return (
    <div
      className={`rounded-lg border p-4 ${
        mejor ? "border-sci-verde/40 bg-sci-verde/5" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
              BADGE_CANAL[canal] ?? "bg-slate-100 text-slate-600"
            }`}
          >
            {c.nombre}
          </span>
          {mejor && <span className="text-xs font-medium text-sci-verde-oscuro">★ mejor</span>}
        </div>
        <div className="text-right">
          <div className="text-base font-semibold text-slate-800">
            {c.intencion > 0 ? soles2(c.costo_por_intencion) : "—"}
          </div>
          <div className="text-[11px] text-slate-400">por intención · costo total {soles2(c.costo)}</div>
        </div>
      </div>

      <div className="mt-3 flex gap-3">
        {etapas.map((e) => {
          const v = e.valor(c);
          const p = pct(v, c.enviados);
          return (
            <div key={e.label} className="flex-1">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">{e.label}</div>
              <div className="text-sm font-semibold tabular-nums text-slate-800">
                {v}
                {e.label !== "Enviados" && e.label !== "Enviadas" && (
                  <span className="ml-1 text-xs font-normal text-slate-400">({p}%)</span>
                )}
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full" style={{ width: `${p}%`, background: e.color }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function EfectividadCanalPanel({
  canales,
}: {
  canales: Record<string, CanalEfectividad>;
}) {
  const filas = Object.entries(canales).sort(
    ([a], [b]) => (CANALES_ORDEN.indexOf(a) + 1 || 99) - (CANALES_ORDEN.indexOf(b) + 1 || 99)
  );
  // Mejor canal: menor costo por intención entre los que sí convirtieron.
  const conversores = filas.filter(([, c]) => c.intencion > 0);
  const mejor = conversores.sort((a, b) => a[1].costo_por_intencion - b[1].costo_por_intencion)[0]?.[0];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-800">Efectividad real por canal</h2>
      <p className="mb-3 text-xs text-slate-400">
        Cada canal con su propio embudo. Comparamos qué canal convierte más barato (costo por intención de pago).
      </p>
      {filas.length === 0 ? (
        <div className="flex h-[160px] items-center justify-center text-xs text-slate-400">
          Aún no hay envíos registrados.
        </div>
      ) : (
        <div className="space-y-3">
          {filas.map(([canal, c]) => (
            <TarjetaCanal key={canal} canal={canal} c={c} mejor={canal === mejor} />
          ))}
        </div>
      )}
    </div>
  );
}
