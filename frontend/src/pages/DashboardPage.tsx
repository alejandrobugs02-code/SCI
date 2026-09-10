import { useEffect, useRef, useState } from "react";
import {
  getAnalyticsCanales,
  getAnalyticsCartera,
  getAnalyticsPriorizacion,
  getAnalyticsResumen,
  getAnalyticsSegmentos,
  getHealth,
  getMetricas,
  getPlan,
  syncLlamadas,
  type AnalyticsCartera,
  type AnalyticsPriorizacion,
  type AnalyticsResumen,
  type AnalyticsSegmentos,
  type CampaignMetricas,
  type CanalEfectividad,
  type Health,
  type Plan,
} from "../api";
import IndecopiBanner from "../components/IndecopiBanner";
import ResumenRealPanel from "../components/ResumenRealPanel";
import SegmentosPanel from "../components/SegmentosPanel";
import EfectividadCanalPanel from "../components/EfectividadCanalPanel";
import GapPanel from "../components/GapPanel";
import CarteraRealPanel from "../components/CarteraRealPanel";
import PriorizacionPanel from "../components/PriorizacionPanel";
import ProyeccionPanel from "../components/ProyeccionPanel";

export default function DashboardPage() {
  const [health, setHealth] = useState<Health>();
  const [resumen, setResumen] = useState<AnalyticsResumen>();
  const [canales, setCanales] = useState<Record<string, CanalEfectividad>>();
  const [cartera, setCartera] = useState<AnalyticsCartera>();
  const [prioriza, setPrioriza] = useState<AnalyticsPriorizacion>();
  const [metricas, setMetricas] = useState<CampaignMetricas>();
  const [plan, setPlan] = useState<Plan>();
  const [segmentos, setSegmentos] = useState<AnalyticsSegmentos>();
  const [error, setError] = useState<string>();

  const cargando = useRef(false);

  const cargarVivo = async () => {
    // Evita encimar ciclos: si el anterior sigue en curso, salta este tick.
    if (cargando.current) return;
    cargando.current = true;
    // Sincroniza en segundo plano los resultados de las llamadas (Vapi).
    syncLlamadas().catch(() => {});
    try {
      await Promise.allSettled([
        getAnalyticsResumen().then(setResumen),
        getAnalyticsCanales().then(setCanales),
        getAnalyticsCartera().then(setCartera),
        getAnalyticsPriorizacion().then(setPrioriza),
        getMetricas().then(setMetricas),
      ]);
    } finally {
      cargando.current = false;
    }
  };

  useEffect(() => {
    // Carga una sola vez al montar la página (al entrar o recargar). Sin polling:
    // para ver datos nuevos se recarga la página.
    Promise.all([getHealth(), getPlan()])
      .then(([h, p]) => {
        setHealth(h);
        setPlan(p);
      })
      .catch(() => setError("No se pudieron cargar los datos del backend."));
    getAnalyticsSegmentos().then(setSegmentos).catch(() => {});
    cargarVivo();
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-800">Dashboards</h1>
        <p className="text-sm text-slate-500">
          Resultados reales de la campaña, cartera y prioridades — se actualizan al recargar.
        </p>
      </header>

      {error && (
        <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700 ring-1 ring-red-200">{error}</div>
      )}

      {health && <IndecopiBanner health={health} />}
      {resumen && <ResumenRealPanel resumen={resumen} />}
      {segmentos?.tiene_uplift && <SegmentosPanel data={segmentos} />}

      {canales && metricas && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <EfectividadCanalPanel canales={canales} />
          <GapPanel metricas={metricas} />
        </div>
      )}

      {cartera && <CarteraRealPanel cartera={cartera} />}
      {prioriza && <PriorizacionPanel data={prioriza} />}

      {plan && <ProyeccionPanel plan={plan} resumen={resumen} />}

      {!error && !resumen && <p className="text-sm text-slate-400">Cargando datos…</p>}
    </div>
  );
}
