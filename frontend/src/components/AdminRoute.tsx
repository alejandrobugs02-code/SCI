import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

export default function AdminRoute() {
  const { user } = useAuth();
  return user?.rol === "admin" ? <Outlet /> : <Navigate to="/" replace />;
}
