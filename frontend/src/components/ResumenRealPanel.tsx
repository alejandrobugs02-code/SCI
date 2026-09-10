import { Coins, FileSignature, HandCoins, MessageSquare, Target, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { AnalyticsResumen } from "../api";
import { soles, soles2 } from "../format";

function Kpi({
  icon: Icon,
  label,
  valor,
  sub,
  color,
}: {
  icon: LucideIcon;
  label: string;
  valor: string;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
        <Icon size={15} style={{ color }} /> {label}
      </div>
      <div className="mt-1.5 text-2xl font-bold text-slate-800">{valor}</div>
      {sub && <div className="text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

export default function ResumenRealPanel({ resumen }: { resumen: AnalyticsResumen }) {
  const C = {
    gris: "#6B7280",
    azul: "#0EA5E9",
    naranja: "#F28F00",
    verde: "#00964B",
    oro: "#FAB500",
  };
  return (
    <div>
      <h2 className="mb-3 text-base font-semibold text-slate-800">
        Resultados de la campaña <span className="text-xs font-normal text-slate-400">· datos reales</span>
      </h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Kpi icon={Users} label="Deuda gestionada" valor={soles(resumen.deuda_total)} sub={`${resumen.deudores_total} clientes`} color={C.gris} />
        <Kpi icon={MessageSquare} label="Contactados" valor={`${resumen.contactados}`} sub={`de ${resumen.deudores_total}`} color={C.azul} />
        <Kpi icon={Target} label="Tasa de respuesta" valor={`${resumen.tasa_respuesta}%`} sub={`${resumen.respondidos} respondieron`} color={C.naranja} />
        <Kpi icon={HandCoins} label="Intención de pago" valor={`${resumen.intencion}`} sub={soles(resumen.monto_intencion)} color={C.verde} />
        <Kpi icon={Coins} label="Costo / intención" valor={resumen.costo_por_intencion ? soles2(resumen.costo_por_intencion) : "—"} sub={`${soles2(resumen.costo_real)} total`} color={C.gris} />
        <Kpi icon={FileSignature} label="Promesas de pago" valor={`${resumen.promesas}`} sub={soles(resumen.monto_prometido)} color={C.oro} />
      </div>
    </div>
  );
}
