import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="p-8 text-sm text-slate-400">Cargando…</div>;
  }
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
