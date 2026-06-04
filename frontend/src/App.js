import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { BusinessProfileProvider } from "@/contexts/BusinessProfileContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
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
    <ErrorBoundary>
      <AuthProvider>
        <BusinessProfileProvider>
          <BrowserRouter>
            <Toaster richColors position="top-right" />
          <Routes>
          <Route path="/login" element={<ErrorBoundary><Login /></ErrorBoundary>} />
          <Route path="/forbidden" element={<ErrorBoundary><Forbidden /></ErrorBoundary>} />
          <Route path="/" element={<ErrorBoundary><RootRedirect /></ErrorBoundary>} />

          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={
              <ProtectedRoute roles={["admin", "viewer"]}><ErrorBoundary><Dashboard /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/stock" element={<ErrorBoundary><LiveStock /></ErrorBoundary>} />
            <Route path="/alerts" element={<ErrorBoundary><Alerts /></ErrorBoundary>} />
            <Route path="/purchases" element={
              <ProtectedRoute roles={["admin", "staff", "viewer"]}><ErrorBoundary><Purchases /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/usage" element={
              <ProtectedRoute roles={["admin", "staff", "viewer"]}><ErrorBoundary><DailyUsage /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/sales" element={
              <ProtectedRoute roles={["admin", "staff", "viewer"]}><ErrorBoundary><Sales /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/items" element={
              <ProtectedRoute roles={["admin"]}><ErrorBoundary><Items /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/expenses" element={
              <ProtectedRoute roles={["admin", "staff", "viewer"]}><ErrorBoundary><Expenses /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/salaries" element={
              <ProtectedRoute roles={["admin", "viewer"]}><ErrorBoundary><Salaries /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/pnl" element={
              <ProtectedRoute roles={["admin", "viewer"]}><ErrorBoundary><PnL /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/settings" element={
              <ProtectedRoute roles={["admin"]}><ErrorBoundary><Settings /></ErrorBoundary></ProtectedRoute>
            } />
            <Route path="/display" element={
              <ProtectedRoute roles={["admin", "viewer"]}><ErrorBoundary><DisplayMode /></ErrorBoundary></ProtectedRoute>
            } />
          </Route>

          <Route path="*" element={<ErrorBoundary><Navigate to="/" replace /></ErrorBoundary>} />
          </Routes>
        </BrowserRouter>
      </BusinessProfileProvider>
    </AuthProvider>
    </ErrorBoundary>
  );
}
