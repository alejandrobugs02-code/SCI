import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CarteraRow } from "../api";
import { soles2 } from "../format";
import { CANALES_ORDEN, COLOR_CANAL, NOMBRE_CANAL } from "../theme";

export default function CarteraPanel({ cartera }: { cartera: CarteraRow[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-800">
        Cartera por tramo de mora × canal
      </h2>
      <p className="mb-4 text-xs text-slate-400">
        Monto en riesgo (S/) en cada tramo de mora, según el canal que asigna el
        orquestador. Útil para dimensionar la operación por canal.
      </p>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={cartera} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
          <XAxis dataKey="tramo" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} unit=" S/" />
          <Tooltip formatter={(v: number, n) => [soles2(v), NOMBRE_CANAL[n as string] ?? n]} />
          <Legend />
          {CANALES_ORDEN.map((canal) => (
            <Bar
              key={canal}
              dataKey={canal}
              stackId="cartera"
              name={NOMBRE_CANAL[canal]}
              fill={COLOR_CANAL[canal]}
              radius={canal === "visita" ? [4, 4, 0, 0] : [0, 0, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
