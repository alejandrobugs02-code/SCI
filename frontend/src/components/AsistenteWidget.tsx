import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, X } from "lucide-react";
import { chatAsistente, type ChatTurno } from "../api";

const SUGERENCIAS = [
  "¿Cómo van los resultados de la campaña?",
  "¿Qué canal es más rentable hoy?",
  "¿A quién debería priorizar?",
  "¿Cómo agrego un cliente nuevo?",
];

export default function AsistenteWidget() {
  const [abierto, setAbierto] = useState(false);
  const [mensajes, setMensajes] = useState<ChatTurno[]>([]);
  const [input, setInput] = useState("");
  const [pensando, setPensando] = useState(false);
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes, pensando]);

  const enviar = async (texto: string) => {
    const msg = texto.trim();
    if (!msg || pensando) return;
    const previos = [...mensajes, { role: "user", content: msg } as ChatTurno];
    setMensajes(previos);
    setInput("");
    setPensando(true);
    try {
      const respuesta = await chatAsistente(msg, previos.slice(0, -1));
      setMensajes([...previos, { role: "assistant", content: respuesta }]);
    } catch {
      setMensajes([
        ...previos,
        { role: "assistant", content: "Tuve un problema al responder. Intenta de nuevo." },
      ]);
    } finally {
      setPensando(false);
    }
  };

  return (
    <>
      {/* Botón flotante */}
      <button
        onClick={() => setAbierto((v) => !v)}
        title="Asistente IA de SCI"
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-sci-verde text-white shadow-lg transition hover:bg-sci-verde-oscuro hover:brightness-110"
      >
        {abierto ? <X size={24} /> : <Sparkles size={24} />}
      </button>

      {/* Panel de chat */}
      {abierto && (
        <div className="fixed bottom-24 right-6 z-50 flex h-[32rem] w-[24rem] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <header className="flex items-center gap-2 bg-sci-verde-oscuro px-4 py-3 text-white">
            <Bot size={20} />
            <div className="leading-tight">
              <p className="text-sm font-semibold">SCI IA</p>
              <p className="text-[11px] text-white/70">Analista de cobranza</p>
            </div>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-4">
            {mensajes.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-slate-500">
                  Hola 👋 Pregúntame por los resultados, el mejor canal, a quién priorizar o
                  cómo usar el sistema.
                </p>
                <div className="flex flex-wrap gap-2">
                  {SUGERENCIAS.map((s) => (
                    <button
                      key={s}
                      onClick={() => enviar(s)}
                      className="rounded-full border border-sci-verde/40 bg-white px-3 py-1.5 text-xs font-medium text-sci-verde-oscuro hover:bg-sci-verde/10"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {mensajes.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm ${
                    m.role === "user"
                      ? "bg-sci-verde text-white"
                      : "bg-white text-slate-700 ring-1 ring-slate-200"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}

            {pensando && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-white px-3.5 py-2 text-sm text-slate-400 ring-1 ring-slate-200">
                  Pensando…
                </div>
              </div>
            )}
            <div ref={finRef} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              enviar(input);
            }}
            className="flex items-center gap-2 border-t border-slate-200 p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Escribe tu pregunta…"
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sci-verde focus:outline-none focus:ring-1 focus:ring-sci-verde"
            />
            <button
              type="submit"
              disabled={!input.trim() || pensando}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sci-verde text-white hover:bg-sci-verde-oscuro disabled:opacity-40"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
