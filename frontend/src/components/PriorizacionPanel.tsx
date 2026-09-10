import { useState } from "react";
import { ChevronLeft, ChevronRight, HandCoins, PhoneOff } from "lucide-react";
import type { AnalyticsPriorizacion, DeudorPrioridad } from "../api";
import { soles } from "../format";

const POR_PAGINA = 8;

function ListaPaginada({
  items,
  vacio,
  derecha,
}: {
  items: DeudorPrioridad[];
  vacio: string;
  derecha: (d: DeudorPrioridad) => React.ReactNode;
}) {
  const [page, setPage] = useState(0);
  if (items.length === 0) {
    return <div className="py-6 text-center text-xs text-slate-400">{vacio}</div>;
  }
  const paginas = Math.ceil(items.length / POR_PAGINA);
  const visibles = items.slice(page * POR_PAGINA, page * POR_PAGINA + POR_PAGINA);
  return (
    <>
      {visibles.map((d) => (
        <Fila key={d.cliente_id} d={d} derecha={derecha(d)} />
      ))}
      {paginas > 1 && (
        <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex items-center gap-0.5 rounded px-1.5 py-1 hover:bg-slate-100 disabled:opacity-30"
          >
            <ChevronLeft size={14} /> Anterior
          </button>
          <span>
            {page * POR_PAGINA + 1}–{Math.min((page + 1) * POR_PAGINA, items.length)} de{" "}
            {items.length}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(paginas - 1, p + 1))}
            disabled={page >= paginas - 1}
            className="flex items-center gap-0.5 rounded px-1.5 py-1 hover:bg-slate-100 disabled:opacity-30"
          >
            Siguiente <ChevronRight size={14} />
          </button>
        </div>
      )}
    </>
  );
}

function Promesa({ d }: { d: DeudorPrioridad }) {
  if (!d.promesa_monto && !d.promesa_fecha_texto) {
    return <span className="text-xs text-slate-400">sin compromiso aún</span>;
  }
  const monto = d.promesa_monto ? soles(d.promesa_monto) : "—";
  const fecha = d.promesa_fecha ?? d.promesa_fecha_texto;
  return (
    <span className="text-xs font-medium text-sci-verde-oscuro">
      Promete {monto}
      {fecha ? ` · ${fecha}` : ""}
    </span>
  );
}

function Fila({ d, derecha }: { d: DeudorPrioridad; derecha: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 py-2 last:border-0">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-slate-700">{d.nombre || d.cliente_id}</div>
        <div className="text-xs text-slate-400">
          {d.telefono || "sin teléfono"} · {soles(d.monto_deuda)}
        </div>
      </div>
      <div className="shrink-0 text-right">{derecha}</div>
    </div>
  );
}

export default function PriorizacionPanel({ data }: { data: AnalyticsPriorizacion }) {
  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-800">
          <HandCoins size={17} className="text-sci-verde" /> Con intención de pago
        </h2>
        <p className="mb-2 text-xs text-slate-400">Dales seguimiento para cerrar el compromiso.</p>
        <ListaPaginada
          items={data.con_intencion}
          vacio="Aún no hay clientes con intención de pago."
          derecha={(d) => <Promesa d={d} />}
        />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-800">
          <PhoneOff size={17} className="text-red-600" /> Alto riesgo sin contactar
        </h2>
        <p className="mb-2 text-xs text-slate-400">Prioridad de contacto, ordenados por monto.</p>
        <ListaPaginada
          items={data.alto_riesgo_sin_contactar}
          vacio="Todos los de alto riesgo ya fueron contactados."
          derecha={(d) => (
            <span className="text-xs font-medium text-red-600">{d.dias_mora ?? 0} d mora</span>
          )}
        />
      </div>
    </div>
  );
}
