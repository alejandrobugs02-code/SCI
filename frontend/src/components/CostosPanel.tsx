import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CampaignMetricas, Plan } from "../api";
import { soles2 } from "../format";
import { SCI } from "../theme";

export default function CostosPanel({
  plan,
  metricas,
}: {
  plan: Plan;
  metricas: CampaignMetricas;
}) {
  const meta = plan.ahorro_pct >= 10;
  const comp = [
    { nombre: "Modelo tradicional", costo: plan.costo_baseline, color: SCI.gris },
    { nombre: "SCI (IA)", costo: plan.costo_optimizado, color: SCI.verde },
  ];
  const meses = metricas.gasto_por_mes;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-800">
            Optimización de costos de cobranza
          </h2>
          <p className="text-xs text-slate-400">
            Proyección de ahorro y gasto mensual real generado en cobranzas.
          </p>
        </div>
        <div
          className={`rounded-xl px-4 py-2 text-right ${
            meta ? "bg-sci-verde/10" : "bg-amber-50"
          }`}
        >
          <p className="text-3xl font-extrabold text-sci-verde">−{plan.ahorro_pct}%</p>
          <p className="text-xs font-medium text-slate-500">ahorro ({soles2(plan.ahorro_soles)})</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium text-slate-500">
            Costo de campaña: tradicional vs. IA
          </p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={comp} margin={{ top: 20, right: 10, bottom: 0, left: -10 }}>
              <XAxis dataKey="nombre" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit=" S/" />
              <Tooltip formatter={(v: number) => soles2(v)} />
              <Bar dataKey="costo" radius={[6, 6, 0, 0]}>
                <LabelList dataKey="costo" position="top" formatter={(v: number) => soles2(v)} style={{ fontSize: 11, fill: "#475569" }} />
                {comp.map((d) => (
                  <Cell key={d.nombre} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500">Gasto mensual real (en cobranzas)</p>
            <p className="text-xs text-slate-400">
              acumulado <span className="font-semibold text-slate-600">{soles2(metricas.costo_acumulado)}</span>
            </p>
          </div>
          {meses.length === 0 ? (
            <div className="flex h-[200px] items-center justify-center rounded-lg bg-slate-50 text-center text-xs text-slate-400">
              Aún no hay gasto real. Inicia envíos desde<br />Base de datos para ver el consumo mensual.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={meses} margin={{ top: 20, right: 10, bottom: 0, left: -10 }}>
                <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit=" S/" />
                <Tooltip formatter={(v: number) => soles2(v)} />
                <Bar dataKey="costo" fill={SCI.oro} radius={[6, 6, 0, 0]}>
                  <LabelList dataKey="costo" position="top" formatter={(v: number) => soles2(v)} style={{ fontSize: 10, fill: "#475569" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
