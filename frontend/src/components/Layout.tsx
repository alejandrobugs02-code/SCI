import { Database, LayoutDashboard, LogOut, Settings } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import AsistenteWidget from "./AsistenteWidget";
import LogoSCI from "./LogoSCI";

function NavItem({ to, icon: Icon, label }: { to: string; icon: LucideIcon; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
          isActive
            ? "bg-sci-verde/10 text-sci-verde-oscuro"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        }`
      }
    >
      <Icon size={18} strokeWidth={2} />
      {label}
    </NavLink>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const esAdmin = user?.rol === "admin";

  const salir = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="px-5 pb-1 pt-5">
          <LogoSCI className="h-8 w-auto" />
          <p className="mt-2 text-[10px] font-medium uppercase tracking-wide text-slate-400">
            Sistema de Cobranzas Inteligente
          </p>
        </div>

        <nav className="mt-5 flex-1 space-y-1 px-3">
          <NavItem to="/" icon={LayoutDashboard} label="Dashboards" />
          <NavItem to="/base-datos" icon={Database} label="Base de datos" />
          {esAdmin && <NavItem to="/configuracion" icon={Settings} label="Configuración" />}
        </nav>

        <div className="border-t border-slate-200 p-3">
          <div className="mb-2 px-2">
            <p className="text-sm font-semibold text-slate-700">{user?.nombre}</p>
            <p className="text-xs text-slate-400">
              {esAdmin ? "Super Administrador" : "Usuario Visor"}
            </p>
          </div>
          <button
            onClick={salir}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-red-600"
          >
            <LogOut size={16} /> Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-6xl px-8 py-8">
          <Outlet />
        </div>
      </main>

      <AsistenteWidget />
    </div>
  );
}
