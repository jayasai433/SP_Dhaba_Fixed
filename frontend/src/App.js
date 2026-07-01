import React, { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { BusinessProfileProvider, useBusinessProfile } from "@/contexts/BusinessProfileContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Forbidden from "@/pages/Forbidden";

const Sales     = lazy(() => import("@/pages/Sales"));
const Purchases = lazy(() => import("@/pages/Purchases"));
const Expenses  = lazy(() => import("@/pages/Expenses"));
const Items     = lazy(() => import("@/pages/Items"));

import "@/App.css";

function DynamicTitle() {
  const { profile } = useBusinessProfile();
  useEffect(() => {
    if (profile?.name) document.title = `${profile.name}. Ops`;
  }, [profile?.name]);
  return null;
}

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to="/sales" replace />;
}

function Spinner() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600" />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BusinessProfileProvider>
          <DynamicTitle />
          <BrowserRouter>
            <Toaster richColors position="top-right" />
            <Suspense fallback={<Spinner />}>
              <Routes>
                <Route path="/login" element={<ErrorBoundary><Login /></ErrorBoundary>} />
                <Route path="/forbidden" element={<ErrorBoundary><Forbidden /></ErrorBoundary>} />
                <Route path="/" element={<ErrorBoundary><RootRedirect /></ErrorBoundary>} />

                <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
                  <Route path="/sales" element={
                    <ProtectedRoute roles={["admin", "staff", "viewer"]}>
                      <ErrorBoundary><Sales /></ErrorBoundary>
                    </ProtectedRoute>
                  } />
                  <Route path="/purchases" element={
                    <ProtectedRoute roles={["admin", "staff", "viewer"]}>
                      <ErrorBoundary><Purchases /></ErrorBoundary>
                    </ProtectedRoute>
                  } />
                  <Route path="/expenses" element={
                    <ProtectedRoute roles={["admin", "staff", "viewer"]}>
                      <ErrorBoundary><Expenses /></ErrorBoundary>
                    </ProtectedRoute>
                  } />
                  <Route path="/items" element={
                    <ProtectedRoute roles={["admin", "staff"]}>
                      <ErrorBoundary><Items /></ErrorBoundary>
                    </ProtectedRoute>
                  } />
                </Route>

                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </BusinessProfileProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}
