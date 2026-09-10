import { useEffect, useRef, useState } from "react";
import {
  Download,
  FileWarning,
  MessageCircle,
  Pencil,
  Phone,
  Play,
  Send,
  Upload,
  UserPlus,
  X,
} from "lucide-react";
import {
  crearDeudor,
  descargarReporteGestionHumana,
  ejecutarEstrategias,
  enviarCampania,
  getDeudores,
  importarDeudores,
  updateDeudor,
  type Deudor,
  type DeudoresPagina,
  type EjecucionResumen,
} from "../api";
import { useAuth } from "../auth";
import { soles } from "../format";
import { BADGE_CANAL, NOMBRE_CANAL } from "../theme";

type Toast = { tipo: "ok" | "error"; msg: string } | null;

const PER_PAGE = 50;

const COLOR_RIESGO: Record<string, string> = {
  bajo: "text-emerald-600",
  medio: "text-amber-600",
  alto: "text-red-600",
};

function extraerError(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  return d || "Ocurrió un error.";
}

export default function BaseDatosPage() {
  const { user } = useAuth();
  const esAdmin = user?.rol === "admin";
  const [data, setData] = useState<DeudoresPagina>();
  const [error, setError] = useState<string>();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [toast, setToast] = useState<Toast>(null);
  const [enviando, setEnviando] = useState<string>("");
  const [editar, setEditar] = useState<Deudor | null>(null);
  const [nuevo, setNuevo] = useState(false);
  const [simular, setSimular] = useState(true);
  const [ejecutando, setEjecutando] = useState(false);
  const [resumen, setResumen] = useState<EjecucionResumen | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const cargar = (busqueda = q, pagina = page) =>
    getDeudores(busqueda, pagina * PER_PAGE, PER_PAGE)
      .then(setData)
      .catch(() => setError("No se pudo cargar la base de datos."));

  // Busca/pagina en el servidor (con debounce para no disparar en cada tecla).
  useEffect(() => {
    const t = setTimeout(() => cargar(q, page), 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, page]);

  const notificar = (t: Toast) => {
    setToast(t);
    setTimeout(() => setToast(null), 3500);
  };

  const enviar = async (d: Deudor, canal: string) => {
    setEnviando(`${d.id}-${canal}`);
    try {
      await enviarCampania(d.id, canal);
      notificar({ tipo: "ok", msg: `Enviado a ${d.nombre || d.cliente_id} por ${canal}.` });
    } catch (e) {
      notificar({ tipo: "error", msg: extraerError(e) });
    } finally {
      setEnviando("");
    }
  };

  const importar = async (file: File) => {
    try {
      const res = await importarDeudores(file, false);
      notificar({ tipo: "ok", msg: `Importados: ${res.creados} nuevos, ${res.actualizados} actualizados.` });
      cargar();
    } catch (e) {
      notificar({ tipo: "error", msg: extraerError(e) });
    }
  };

  const ejecutar = async () => {
    setEjecutando(true);
    try {
      const res = await ejecutarEstrategias(simular);
      setResumen(res);
    } catch (e) {
      notificar({ tipo: "error", msg: extraerError(e) });
    } finally {
      setEjecutando(false);
    }
  };

  const descargarReporte = async () => {
    try {
      await descargarReporteGestionHumana();
    } catch {
      notificar({ tipo: "error", msg: "No se pudo descargar el reporte." });
    }
  };

  const filtrados = data?.items;
  const total = data?.total ?? 0;
  const totalPaginas = Math.max(1, Math.ceil(total / PER_PAGE));

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Base de datos</h1>
          <p className="text-sm text-slate-500">
            {data ? `${total.toLocaleString()} clientes` : "Cargando…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={q}
            onChange={(e) => {
              setPage(0);
              setQ(e.target.value);
            }}
            placeholder="Buscar nombre, ID, DNI o teléfono…"
            className="w-64 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
          />
          {esAdmin && (
            <>
              <label
                title="Simular no envía nada real: registra los envíos para ver el efecto en los dashboards sin consumir créditos."
                className="flex select-none items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-medium text-slate-500"
              >
                <input
                  type="checkbox"
                  checked={simular}
                  onChange={(e) => setSimular(e.target.checked)}
                  className="accent-sci-verde"
                />
                Simular
              </label>
              <button
                onClick={ejecutar}
                disabled={ejecutando}
                className="flex items-center gap-2 rounded-lg bg-sci-verde-oscuro px-3 py-2 text-sm font-semibold text-white hover:brightness-110 disabled:opacity-60"
              >
                <Play size={16} /> {ejecutando ? "Ejecutando…" : "Ejecutar estrategias"}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) importar(f);
                  e.target.value = "";
                }}
              />
              <button
                onClick={() => fileRef.current?.click()}
                className="flex items-center gap-2 rounded-lg border border-sci-verde px-3 py-2 text-sm font-medium text-sci-verde-oscuro hover:bg-sci-verde/10"
              >
                <Upload size={16} /> Importar XLSX
              </button>
              <button
                onClick={() => setNuevo(true)}
                className="flex items-center gap-2 rounded-lg bg-sci-verde px-3 py-2 text-sm font-semibold text-white hover:bg-sci-verde-oscuro"
              >
                <UserPlus size={16} /> Nuevo cliente
              </button>
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700 ring-1 ring-red-200">{error}</div>
      )}

      {filtrados && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
                <th className="px-3 py-2.5">Cliente</th>
                <th className="px-3 py-2.5">Teléfono</th>
                <th className="px-3 py-2.5">Deuda</th>
                <th className="px-3 py-2.5">Mora</th>
                <th className="px-3 py-2.5">Riesgo</th>
                <th className="px-3 py-2.5">Canal asignado</th>
                <th className="px-3 py-2.5 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((d) => (
                <tr key={d.id} className="border-b border-slate-100 hover:bg-slate-50/60">
                  <td className="px-3 py-2.5">
                    <div className="font-medium text-slate-800">{d.nombre || "—"}</div>
                    <div className="text-xs text-slate-400">
                      {d.cliente_id} · {d.region}
                      {d.opt_out && <span className="ml-1 text-red-500">opt-out</span>}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {d.telefono || <span className="text-amber-500">falta</span>}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {d.monto_deuda ? soles(d.monto_deuda) : <span className="text-amber-500">falta</span>}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">{d.dias_mora} d</td>
                  <td className={`px-3 py-2.5 font-medium capitalize ${COLOR_RIESGO[d.riesgo] ?? ""}`}>
                    {d.riesgo}
                  </td>
                  <td className="px-3 py-2.5">
                    {d.recomendacion.accion === "no_contactar" ? (
                      <span
                        title={d.recomendacion.motivo}
                        className="inline-block w-fit rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 ring-1 ring-red-200"
                      >
                        Excluido (opt-out)
                      </span>
                    ) : (
                      <div className="flex flex-col gap-0.5">
                        <span
                          title={d.recomendacion.motivo}
                          className={`inline-block w-fit rounded-full px-2.5 py-1 text-xs font-medium ${
                            BADGE_CANAL[d.recomendacion.canal] ?? "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {d.recomendacion.nombre}
                        </span>
                        {d.recomendacion.uplift != null && d.recomendacion.segmento && (
                          <span className="text-[11px] text-slate-400">
                            uplift {d.recomendacion.uplift >= 0 ? "+" : ""}
                            {d.recomendacion.uplift.toFixed(2)}
                          </span>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {esAdmin ? (
                      <div className="flex items-center justify-end gap-1">
                        <BotonAccion
                          title="Enviar SMS"
                          icon={Send}
                          disabled={!d.telefono || d.opt_out || enviando === `${d.id}-sms`}
                          onClick={() => enviar(d, "sms")}
                        />
                        <BotonAccion
                          title="Iniciar WhatsApp"
                          icon={MessageCircle}
                          disabled={!d.telefono || d.opt_out || !d.canal_whatsapp || enviando === `${d.id}-whatsapp`}
                          onClick={() => enviar(d, "whatsapp")}
                        />
                        <BotonAccion
                          title="Llamada de Voz IA"
                          icon={Phone}
                          disabled={!d.telefono || d.opt_out || enviando === `${d.id}-voz_ai`}
                          onClick={() => enviar(d, "voz_ai")}
                        />
                        <BotonAccion title="Editar" icon={Pencil} onClick={() => setEditar(d)} />
                      </div>
                    ) : (
                      <span className="text-xs text-slate-300">solo lectura</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtrados.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-slate-400">Sin resultados.</p>
          )}
        </div>
      )}

      {data && total > PER_PAGE && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            Página {page + 1} de {totalPaginas}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium hover:bg-slate-50 disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPaginas - 1, p + 1))}
              disabled={page >= totalPaginas - 1}
              className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium hover:bg-slate-50 disabled:opacity-40"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}

      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 rounded-lg px-4 py-3 text-sm text-white shadow-lg ${
            toast.tipo === "ok" ? "bg-sci-verde" : "bg-red-600"
          }`}
        >
          {toast.msg}
        </div>
      )}

      {editar && (
        <EditarModal
          deudor={editar}
          onClose={() => setEditar(null)}
          onSaved={() => {
            setEditar(null);
            cargar();
            notificar({ tipo: "ok", msg: "Cliente actualizado." });
          }}
          onError={(m) => notificar({ tipo: "error", msg: m })}
        />
      )}

      {nuevo && (
        <NuevoModal
          onClose={() => setNuevo(false)}
          onSaved={(d) => {
            setNuevo(false);
            cargar();
            notificar({ tipo: "ok", msg: `Cliente ${d.nombre || d.cliente_id} agregado.` });
          }}
          onError={(m) => notificar({ tipo: "error", msg: m })}
        />
      )}

      {resumen && (
        <ResumenEjecucionModal
          resumen={resumen}
          onClose={() => setResumen(null)}
          onDescargar={descargarReporte}
        />
      )}
    </div>
  );
}

const CANAL_ICONO: Record<string, typeof Send> = {
  whatsapp: MessageCircle,
  sms: Send,
  voz_ai: Phone,
};

function ResumenEjecucionModal({
  resumen,
  onClose,
  onDescargar,
}: {
  resumen: EjecucionResumen;
  onClose: () => void;
  onDescargar: () => void;
}) {
  const totalAutomatizado = Object.values(resumen.colas).reduce((s, c) => s + c.enviados, 0);
  const humana = resumen.gestion_humana;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-800">Estrategias ejecutadas</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>
        <p className="mb-4 text-xs text-slate-400">
          {resumen.simulado
            ? "Modo simulación: envíos registrados sin consumir créditos."
            : "Envío real: se contactó a los clientes por sus canales."}
        </p>

        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Canales automatizados · {totalAutomatizado} envíos en 3 colas
        </p>
        <div className="grid grid-cols-3 gap-3">
          {["whatsapp", "sms", "voz_ai"].map((canal) => {
            const c = resumen.colas[canal] ?? { total: 0, enviados: 0, fallidos: 0 };
            const Icon = CANAL_ICONO[canal] ?? Send;
            return (
              <div key={canal} className="rounded-xl border border-slate-200 p-3 text-center">
                <Icon size={18} className="mx-auto text-sci-verde" />
                <div className="mt-1 text-2xl font-bold text-slate-800">{c.enviados}</div>
                <div className="text-[11px] text-slate-500">{NOMBRE_CANAL[canal]}</div>
                {c.fallidos > 0 && (
                  <div className="text-[11px] text-red-500">{c.fallidos} fallidos</div>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-4 rounded-xl bg-amber-50 p-4 ring-1 ring-amber-200">
          <div className="flex items-start gap-2">
            <FileWarning size={18} className="mt-0.5 shrink-0 text-amber-600" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-800">
                {humana.total} requieren gestión humana o de campo
              </p>
              <p className="mt-0.5 text-xs text-amber-700">
                Llamada humana y visita no se automatizan. Descarga el reporte con sus datos
                para asignarlos a un gestor.
              </p>
              {humana.total > 0 && (
                <button
                  onClick={onDescargar}
                  className="mt-3 flex items-center gap-2 rounded-lg bg-amber-600 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-700"
                >
                  <Download size={16} /> Descargar reporte (CSV)
                </button>
              )}
            </div>
          </div>
        </div>

        {resumen.suprimidos > 0 && (
          <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs text-slate-500 ring-1 ring-slate-200">
            <span className="font-semibold text-slate-700">{resumen.suprimidos} suprimidos</span>{" "}
            por el motor de incrementalidad: contactarlos no mejora el pago, así que se omiten
            para no gastar sin retorno.
          </div>
        )}
        {resumen.excluidos > 0 && (
          <p className="mt-3 text-xs text-slate-400">
            {resumen.excluidos} excluidos por opt-out / sin consentimiento.
          </p>
        )}
      </div>
    </div>
  );
}

function BotonAccion({
  title,
  icon: Icon,
  onClick,
  disabled,
}: {
  title: string;
  icon: typeof Send;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      disabled={disabled}
      className="rounded-md p-2 text-slate-500 hover:bg-sci-verde/10 hover:text-sci-verde-oscuro disabled:cursor-not-allowed disabled:opacity-30"
    >
      <Icon size={16} />
    </button>
  );
}

function EditarModal({
  deudor,
  onClose,
  onSaved,
  onError,
}: {
  deudor: Deudor;
  onClose: () => void;
  onSaved: (d: Deudor) => void;
  onError: (m: string) => void;
}) {
  const [nombre, setNombre] = useState(deudor.nombre);
  const [telefono, setTelefono] = useState(deudor.telefono);
  const [documento, setDocumento] = useState(deudor.documento);
  const [monto, setMonto] = useState(deudor.monto_deuda);
  const [guardando, setGuardando] = useState(false);

  const guardar = async () => {
    setGuardando(true);
    try {
      const d = await updateDeudor(deudor.id, {
        nombre,
        telefono,
        documento,
        monto_deuda: monto,
      });
      onSaved(d);
    } catch (e) {
      onError(extraerError(e));
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-800">Editar cliente</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>
        <p className="mb-4 text-xs text-slate-400">{deudor.cliente_id}</p>
        <div className="space-y-3">
          <Campo label="Nombre" value={nombre} onChange={setNombre} />
          <Campo label="Teléfono (E.164, ej. +51987654321)" value={telefono} onChange={setTelefono} />
          <Campo label="Documento (DNI)" value={documento} onChange={setDocumento} />
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">Monto de deuda (S/)</label>
            <input
              type="number"
              value={monto}
              onChange={(e) => setMonto(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
            />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100">
            Cancelar
          </button>
          <button
            onClick={guardar}
            disabled={guardando}
            className="rounded-lg bg-sci-verde px-4 py-2 text-sm font-semibold text-white hover:bg-sci-verde-oscuro disabled:opacity-60"
          >
            {guardando ? "Guardando…" : "Guardar"}
          </button>
        </div>
      </div>
    </div>
  );
}

function NuevoModal({
  onClose,
  onSaved,
  onError,
}: {
  onClose: () => void;
  onSaved: (d: Deudor) => void;
  onError: (m: string) => void;
}) {
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [documento, setDocumento] = useState("");
  const [monto, setMonto] = useState(0);
  const [diasMora, setDiasMora] = useState(0);
  const [riesgo, setRiesgo] = useState("medio");
  const [region, setRegion] = useState("");
  const [guardando, setGuardando] = useState(false);

  const guardar = async () => {
    if (!nombre.trim()) {
      onError("El nombre es obligatorio.");
      return;
    }
    setGuardando(true);
    try {
      const d = await crearDeudor({
        nombre,
        telefono,
        documento,
        monto_deuda: monto,
        dias_mora: diasMora,
        riesgo,
        region,
      });
      onSaved(d);
    } catch (e) {
      onError(extraerError(e));
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-800">Nuevo cliente</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>
        <p className="mb-4 text-xs text-slate-400">Se le asignará un ID automático y el canal según mora y riesgo.</p>
        <div className="space-y-3">
          <Campo label="Nombre" value={nombre} onChange={setNombre} />
          <Campo label="Teléfono (E.164, ej. +51987654321)" value={telefono} onChange={setTelefono} />
          <Campo label="Documento (DNI)" value={documento} onChange={setDocumento} />
          <Campo label="Región" value={region} onChange={setRegion} />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-600">Monto de deuda (S/)</label>
              <input
                type="number"
                value={monto}
                onChange={(e) => setMonto(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-600">Días de mora</label>
              <input
                type="number"
                value={diasMora}
                onChange={(e) => setDiasMora(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">Riesgo</label>
            <select
              value={riesgo}
              onChange={(e) => setRiesgo(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
            >
              <option value="bajo">Bajo</option>
              <option value="medio">Medio</option>
              <option value="alto">Alto</option>
            </select>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100">
            Cancelar
          </button>
          <button
            onClick={guardar}
            disabled={guardando}
            className="rounded-lg bg-sci-verde px-4 py-2 text-sm font-semibold text-white hover:bg-sci-verde-oscuro disabled:opacity-60"
          >
            {guardando ? "Guardando…" : "Agregar cliente"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Campo({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-600">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
      />
    </div>
  );
}
