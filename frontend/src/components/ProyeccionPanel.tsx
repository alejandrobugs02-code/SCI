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
import type { AnalyticsResumen, Plan } from "../api";
import { soles, soles2 } from "../format";
import { SCI } from "../theme";

function Tarjeta({
  titulo,
  valor,
  desc,
  color,
}: {
  titulo: string;
  valor: string;
  desc: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <p className="text-xs font-medium text-slate-500">{titulo}</p>
      <p className="mt-1 text-2xl font-bold" style={{ color }}>
        {valor}
      </p>
      <p className="mt-1 text-xs text-slate-400">{desc}</p>
    </div>
  );
}

export default function ProyeccionPanel({
  plan,
  resumen,
}: {
  plan: Plan;
  resumen?: AnalyticsResumen;
}) {
  const roi =
    plan.costo_optimizado > 0 ? Math.round(plan.recupero_esperado / plan.costo_optimizado) : 0;
  const comp = [
    { nombre: "Tradicional", costo: plan.costo_baseline, color: SCI.gris },
    { nombre: "SCI (IA)", costo: plan.costo_optimizado, color: SCI.verde },
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-800">Proyección de la estrategia</h2>
      <p className="mb-4 text-xs text-slate-400">
        Estimado de costo y recupero <strong>si gestionas a los {plan.deudores_gestionados} clientes</strong> con el
        canal óptimo que recomienda el orquestador. Es una proyección del plan, no lo ya gastado.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Tarjeta
          titulo="Costo: modelo tradicional"
          valor={soles(plan.costo_baseline)}
          desc="Todo con llamada humana y visita de campo (lo de antes)."
          color={SCI.gris}
        />
        <Tarjeta
          titulo="Costo: SCI (IA)"
          valor={soles(plan.costo_optimizado)}
          desc="Cada cliente por su canal óptimo: WhatsApp → SMS → Voz IA → humano → campo."
          color={SCI.verde}
        />
        <Tarjeta
          titulo="Ahorro proyectado"
          valor={`−${plan.ahorro_pct}%`}
          desc={`${soles(plan.ahorro_soles)} menos que el modelo tradicional.`}
          color={SCI.verde}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium text-slate-500">Costo de la campaña: tradicional vs. IA</p>
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={comp} margin={{ top: 20, right: 10, bottom: 0, left: -10 }}>
              <XAxis dataKey="nombre" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit=" S/" />
              <Tooltip formatter={(v: number) => soles2(v)} />
              <Bar dataKey="costo" radius={[6, 6, 0, 0]}>
                <LabelList
                  dataKey="costo"
                  position="top"
                  formatter={(v: number) => soles2(v)}
                  style={{ fontSize: 11, fill: "#475569" }}
                />
                {comp.map((d) => (
                  <Cell key={d.nombre} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col justify-center gap-3">
          <div className="rounded-lg bg-sci-verde/5 p-4">
            <p className="text-xs font-medium text-slate-500">Recupero esperado</p>
            <p className="text-2xl font-bold text-sci-verde">{soles(plan.recupero_esperado)}</p>
            <p className="text-xs text-slate-400">
              ≈ {roi}× el costo de contacto proyectado (tasa de pago estimada × deuda).
            </p>
          </div>
          {resumen && (
            <div className="rounded-lg bg-slate-50 p-4 text-xs text-slate-500">
              <span className="font-semibold text-slate-600">Hasta ahora (real):</span>{" "}
              {resumen.contactados} contactados · {soles2(resumen.costo_real)} gastado ·{" "}
              <span className="font-medium text-sci-verde-oscuro">
                {resumen.intencion} con intención de pago ({soles(resumen.monto_intencion)})
              </span>
              .
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
