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
import type { Plan } from "../api";
import { soles2 } from "../format";
import { COLOR_CANAL } from "../theme";

export default function CostoPorCanalPanel({ plan }: { plan: Plan }) {
  const data = Object.entries(plan.por_canal)
    .map(([canal, v]) => ({
      canal,
      nombre: v.nombre,
      costo: v.costo,
      deudores: v.deudores,
    }))
    .sort((a, b) => b.costo - a.costo);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-800">
        Costo a pagar por canal
      </h2>
      <p className="mb-3 text-xs text-slate-400">
        Lo que costaría contactar a toda la base de datos según el canal asignado (S/).
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart layout="vertical" data={data} margin={{ top: 0, right: 48, bottom: 0, left: 30 }}>
          <XAxis type="number" tick={{ fontSize: 11 }} unit=" S/" />
          <YAxis type="category" dataKey="nombre" tick={{ fontSize: 11 }} width={110} />
          <Tooltip
            formatter={(v: number, _n, p) => [`${soles2(v)} · ${p.payload.deudores} deudores`, "Costo"]}
          />
          <Bar dataKey="costo" radius={[0, 4, 4, 0]}>
            <LabelList dataKey="costo" position="right" formatter={(v: number) => soles2(v)} style={{ fontSize: 10, fill: "#475569" }} />
            {data.map((d) => (
              <Cell key={d.canal} fill={COLOR_CANAL[d.canal] ?? "#94a3b8"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 flex justify-between border-t border-slate-100 pt-2 text-sm">
        <span className="text-slate-500">Total base de datos</span>
        <span className="font-semibold text-slate-800">{soles2(plan.costo_optimizado)}</span>
      </div>
    </div>
  );
}
