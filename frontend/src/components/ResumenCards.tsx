import type { Plan } from "../api";
import { soles } from "../format";

function Card({ titulo, valor, sub }: { titulo: string; valor: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <p className="text-sm font-medium text-slate-500">{titulo}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800">{valor}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

export default function ResumenCards({ plan }: { plan: Plan }) {
  const roi =
    plan.costo_optimizado > 0
      ? (plan.recupero_esperado / plan.costo_optimizado).toFixed(0)
      : "—";
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card
        titulo="Deudores gestionados"
        valor={plan.deudores_gestionados.toString()}
        sub={`${plan.excluidos_opt_out} excluido(s) por opt-out`}
      />
      <Card titulo="Deuda total en cartera" valor={soles(plan.deuda_total)} />
      <Card
        titulo="Costo de campaña (optimizado)"
        valor={soles(plan.costo_optimizado)}
        sub="Suma del canal asignado por deudor"
      />
      <Card
        titulo="Recupero esperado"
        valor={soles(plan.recupero_esperado)}
        sub={`≈ ${roi}x el costo de contacto`}
      />
    </div>
  );
}
