import { AlertTriangle } from "lucide-react";
import type { AnalyticsCartera, Grupo } from "../api";
import { soles } from "../format";

const COLOR_RIESGO: Record<string, string> = {
  alto: "#DC2626",
  medio: "#F28F00",
  bajo: "#00964B",
};

function Distribucion({
  titulo,
  grupos,
  colores,
}: {
  titulo: string;
  grupos: Record<string, Grupo>;
  colores?: Record<string, string>;
}) {
  const filas = Object.entries(grupos).sort((a, b) => b[1].monto - a[1].monto);
  const max = Math.max(1, ...filas.map(([, g]) => g.monto));
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{titulo}</h3>
      <div className="space-y-2">
        {filas.map(([k, g]) => (
          <div key={k}>
            <div className="mb-0.5 flex items-center justify-between text-xs">
              <span className="capitalize text-slate-600">
                {k} <span className="text-slate-400">· {g.deudores}</span>
              </span>
              <span className="font-medium text-slate-700">{soles(g.monto)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full"
                style={{ width: `${(g.monto / max) * 100}%`, background: colores?.[k] ?? "#00964B" }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CarteraRealPanel({ cartera }: { cartera: AnalyticsCartera }) {
  const pctRiesgo = cartera.deuda_total
    ? Math.round((cartera.monto_en_riesgo / cartera.deuda_total) * 100)
    : 0;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-800">Cartera (portafolio real)</h2>
          <p className="text-xs text-slate-400">
            {cartera.deudores_total} clientes · {soles(cartera.deuda_total)} en deuda
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 ring-1 ring-red-200">
          <AlertTriangle size={16} className="text-red-600" />
          <div>
            <div className="text-xs text-red-700">Monto en riesgo (prob. default)</div>
            <div className="text-sm font-bold text-red-700">
              {soles(cartera.monto_en_riesgo)} <span className="font-normal">({pctRiesgo}%)</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-x-8 gap-y-5 sm:grid-cols-2">
        <Distribucion titulo="Por riesgo" grupos={cartera.por_riesgo} colores={COLOR_RIESGO} />
        <Distribucion titulo="Por tramo de mora" grupos={cartera.por_tramo_mora} />
        <Distribucion titulo="Por región" grupos={cartera.por_region} />
        <Distribucion titulo="Canal digital" grupos={cartera.digital} />
      </div>
    </div>
  );
}
