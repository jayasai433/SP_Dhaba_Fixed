import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Forbidden from "@/pages/Forbidden";
import Dashboard from "@/pages/Dashboard";
import LiveStock from "@/pages/LiveStock";
import Alerts from "@/pages/Alerts";
import Purchases from "@/pages/Purchases";
import DailyUsage from "@/pages/DailyUsage";
import Sales from "@/pages/Sales";
import Items from "@/pages/Items";
import Settings from "@/pages/Settings";
import DisplayMode from "@/pages/DisplayMode";
import Expenses from "@/pages/Expenses";
import Salaries from "@/pages/Salaries";
import PnL from "@/pages/PnL";
import "@/App.css";

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "viewer") return <Navigate to="/display" replace />;
  if (user.role === "staff") return <Navigate to="/stock" replace />;
  return <Navigate to="/dashboard" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster richColors position="top-right" />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forbidden" element={<Forbidden />} />
          <Route path="/" element={<RootRedirect />} />

          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={
              <ProtectedRoute roles={["admin", "viewer"]}><Dashboard /></ProtectedRoute>
            } />
            <Route path="/stock" element={<LiveStock />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/purchases" element={
              <ProtectedRoute roles={["admin", "staff", "viewer"]}><Purchases /></ProtectedRoute>
            } />
            <Route path="/usage" element={
              <ProtectedRoute roles={["admin", "staff", "viewer"]}><DailyUsage /></ProtectedRoute>
            } />
            <Route path="/sales" element={
              <ProtectedRoute roles={["admin", "staff", "viewer"]}><Sales /></ProtectedRoute>
            } />
            <Route path="/items" element={
              <ProtectedRoute roles={["admin"]}><Items /></ProtectedRoute>
            } />
            <Route path="/expenses" element={
              <ProtectedRoute roles={["admin", "staff", "viewer"]}><Expenses /></ProtectedRoute>
            } />
            <Route path="/salaries" element={
              <ProtectedRoute roles={["admin", "viewer"]}><Salaries /></ProtectedRoute>
            } />
            <Route path="/pnl" element={
              <ProtectedRoute roles={["admin", "viewer"]}><PnL /></ProtectedRoute>
            } />
            <Route path="/settings" element={
              <ProtectedRoute roles={["admin"]}><Settings /></ProtectedRoute>
            } />
            <Route path="/display" element={
              <ProtectedRoute roles={["admin", "viewer"]}><DisplayMode /></ProtectedRoute>
            } />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
