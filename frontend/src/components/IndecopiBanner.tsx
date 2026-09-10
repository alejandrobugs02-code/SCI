import type { Health } from "../api";

export default function IndecopiBanner({ health }: { health: Health }) {
  const ok = health.ventana_contacto.permitido;
  return (
    <div
      className={`flex items-center gap-3 rounded-lg p-3 text-sm ring-1 ${
        ok
          ? "bg-green-50 text-green-800 ring-green-200"
          : "bg-amber-50 text-amber-800 ring-amber-200"
      }`}
    >
      <span
        className={`h-2.5 w-2.5 shrink-0 rounded-full ${
          ok ? "bg-sci-verde" : "bg-amber-500"
        }`}
      />
      <span>
        <strong>Validador Indecopi:</strong>{" "}
        {ok
          ? "Ventana de contacto ACTIVA (07:00–20:00, L–S)."
          : health.ventana_contacto.motivo}
      </span>
    </div>
  );
}
