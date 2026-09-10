import { useEffect, useState } from "react";
import { getConfig, putConfig, type AppConfig } from "../api";
import { CANALES_ORDEN } from "../theme";

type Estado = "idle" | "guardando" | "guardado" | "error";

const UMBRALES: { campo: keyof AppConfig; label: string; sufijo: string; ayuda: string }[] = [
  { campo: "dias_temprana", label: "Mora temprana hasta (días)", sufijo: "días", ayuda: "Hasta aquí se prioriza canal digital (WhatsApp/SMS)." },
  { campo: "dias_media", label: "Mora media hasta (días)", sufijo: "días", ayuda: "Tramo de Voz AI / humano según monto." },
  { campo: "dias_tardia", label: "Mora tardía hasta (días)", sufijo: "días", ayuda: "Gestión humana; sobre esto, casos críticos." },
  { campo: "monto_riesgo_temprano", label: "Monto refuerzo Voz AI temprano", sufijo: "S/", ayuda: "Mora temprana de alto riesgo y este monto → Voz AI." },
  { campo: "monto_voz_humano", label: "Monto Voz AI → humano (mora media)", sufijo: "S/", ayuda: "Sobre este monto, la mora media va a agente humano." },
  { campo: "monto_visita", label: "Monto para visita de campo", sufijo: "S/", ayuda: "Mora crítica con este monto → visita de campo." },
];

export default function ConfiguracionPage() {
  const [cfg, setCfg] = useState<AppConfig>();
  const [estado, setEstado] = useState<Estado>("idle");
  const [error, setError] = useState<string>();

  useEffect(() => {
    getConfig().then(setCfg).catch(() => setError("No se pudo cargar la configuración."));
  }, []);

  const set = (campo: keyof AppConfig, valor: string | number) =>
    setCfg((c) => (c ? { ...c, [campo]: valor } : c));

  const setCanal = (canal: string, campo: "costo" | "tasa_pago", valor: number) =>
    setCfg((c) =>
      c ? { ...c, canales: { ...c.canales, [canal]: { ...c.canales[canal], [campo]: valor } } } : c
    );

  const guardar = async () => {
    if (!cfg) return;
    setEstado("guardando");
    try {
      const payload: Record<string, unknown> = {
        prompt_whatsapp: cfg.prompt_whatsapp,
        prompt_voz: cfg.prompt_voz,
        dias_temprana: cfg.dias_temprana,
        dias_media: cfg.dias_media,
        dias_tardia: cfg.dias_tardia,
        monto_riesgo_temprano: cfg.monto_riesgo_temprano,
        monto_voz_humano: cfg.monto_voz_humano,
        monto_visita: cfg.monto_visita,
        canales: Object.fromEntries(
          CANALES_ORDEN.map((k) => [k, { costo: cfg.canales[k].costo, tasa_pago: cfg.canales[k].tasa_pago }])
        ),
      };
      const actualizado = await putConfig(payload);
      setCfg(actualizado);
      setEstado("guardado");
      setTimeout(() => setEstado("idle"), 2500);
    } catch {
      setEstado("error");
    }
  };

  if (error) {
    return <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700 ring-1 ring-red-200">{error}</div>;
  }
  if (!cfg) return <p className="text-sm text-slate-400">Cargando configuración…</p>;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Configuración</h1>
          <p className="text-sm text-slate-500">
            Umbrales del orquestador, economía de canales y contexto de los agentes IA.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {estado === "guardado" && <span className="text-sm text-sci-verde">✓ Guardado</span>}
          {estado === "error" && <span className="text-sm text-red-600">Error al guardar</span>}
          <button
            onClick={guardar}
            disabled={estado === "guardando"}
            className="rounded-lg bg-sci-verde px-4 py-2 text-sm font-semibold text-white hover:bg-sci-verde-oscuro disabled:opacity-60"
          >
            {estado === "guardando" ? "Guardando…" : "Guardar cambios"}
          </button>
        </div>
      </header>

      {/* Umbrales */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-800">Umbrales de decisión</h2>
        <p className="mb-4 text-xs text-slate-400">
          Ajusta cómo el orquestador asigna canales por días de mora y monto.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {UMBRALES.map((u) => (
            <div key={u.campo}>
              <label className="mb-1 block text-sm font-medium text-slate-600">{u.label}</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={cfg[u.campo] as number}
                  onChange={(e) => set(u.campo, Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
                />
                <span className="text-xs text-slate-400">{u.sufijo}</span>
              </div>
              <p className="mt-1 text-xs text-slate-400">{u.ayuda}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Economía de canales */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-800">Economía de canales</h2>
        <p className="mb-4 text-xs text-slate-400">
          Costo por contacto y tasa de pago de cada canal (alimentan el ahorro y el costo por canal).
        </p>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
                <th className="px-3 py-2">Canal</th>
                <th className="px-3 py-2">Costo (S/)</th>
                <th className="px-3 py-2">Tasa de pago (0–1)</th>
              </tr>
            </thead>
            <tbody>
              {CANALES_ORDEN.map((k) => (
                <tr key={k} className="border-b border-slate-100">
                  <td className="px-3 py-2 font-medium text-slate-700">{cfg.canales[k]?.nombre ?? k}</td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      step="0.01"
                      value={cfg.canales[k]?.costo ?? 0}
                      onChange={(e) => setCanal(k, "costo", Number(e.target.value))}
                      className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      step="0.01"
                      value={cfg.canales[k]?.tasa_pago ?? 0}
                      onChange={(e) => setCanal(k, "tasa_pago", Number(e.target.value))}
                      className="w-28 rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Prompts */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-800">
          Contexto de entrenamiento de los agentes IA
        </h2>
        <p className="mb-4 text-xs text-slate-400">
          System prompt por canal (tono SCI, reglas de vocabulario y emojis).
        </p>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">Agente WhatsApp</label>
            <textarea
              value={cfg.prompt_whatsapp}
              onChange={(e) => set("prompt_whatsapp", e.target.value)}
              className="h-80 w-full resize-none rounded-lg border border-slate-300 p-3 font-mono text-xs text-slate-700 focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">Agente de Voz</label>
            <textarea
              value={cfg.prompt_voz}
              onChange={(e) => set("prompt_voz", e.target.value)}
              className="h-80 w-full resize-none rounded-lg border border-slate-300 p-3 font-mono text-xs text-slate-700 focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
            />
          </div>
        </div>
      </section>
    </div>
  );
}
