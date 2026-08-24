import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider } from "./context/AuthContext";
import { WebSocketProvider } from "./context/WebSocketContext";
import { Layout } from "./components/layout/Layout";
import { ProtectedRoute } from "./auth/ProtectedRoute";

import Login from "./auth/Login";
import Register from "./auth/Register";
import ForgotPassword from "./auth/ForgotPassword";
import ResetPassword from "./auth/ResetPassword";
import Profile from "./auth/Profile";

import Dashboard from "./pages/Dashboard";
import Alerts from "./pages/Alerts";
import Flows from "./pages/Flows";
import Statistics from "./pages/Statistics";
import SystemHealth from "./pages/SystemHealth";
import Settings from "./pages/Settings";
import ResponseCenter from "./pages/ResponseCenter";
import ResponseHistoryPage from "./pages/ResponseHistoryPage";
import PolicyManager from "./pages/PolicyManager";
import Reports from "./pages/Reports";
import Analytics from "./pages/Analytics";
import ThreatIntelligence from "./pages/ThreatIntelligence";
import IncidentManager from "./pages/IncidentManager";
import NotificationSettings from "./pages/NotificationSettings";
import { AttackSimulation } from "./pages/AttackSimulation";
import { Models } from "./pages/Models";
import { UserManagement } from "./pages/UserManagement";
import { AuditLog } from "./pages/AuditLog";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

// Every protected page declares the one permission it needs (see
// backend/auth/permissions.py's catalog) - ProtectedRoute redirects to
// /login if not authenticated at all, or shows an inline "access denied"
// if authenticated but lacking that permission. Dashboard/Settings need no
// specific permission beyond being logged in.
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <WebSocketProvider>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/reset-password" element={<ResetPassword />} />

                <Route element={<Layout />}>
                  <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                  <Route path="/alerts" element={<ProtectedRoute requiredPermission="alerts:read"><Alerts /></ProtectedRoute>} />
                  <Route path="/flows" element={<ProtectedRoute requiredPermission="flows:read"><Flows /></ProtectedRoute>} />
                  <Route path="/statistics" element={<ProtectedRoute requiredPermission="statistics:read"><Statistics /></ProtectedRoute>} />
                  <Route path="/system-health" element={<ProtectedRoute><SystemHealth /></ProtectedRoute>} />
                  <Route path="/response-center" element={<ProtectedRoute requiredPermission="responses:execute"><ResponseCenter /></ProtectedRoute>} />
                  <Route path="/response-history" element={<ProtectedRoute requiredPermission="responses:read"><ResponseHistoryPage /></ProtectedRoute>} />
                  <Route path="/policy-manager" element={<ProtectedRoute requiredPermission="settings:write"><PolicyManager /></ProtectedRoute>} />
                  <Route path="/reports" element={<ProtectedRoute requiredPermission="reports:read"><Reports /></ProtectedRoute>} />
                  <Route path="/analytics" element={<ProtectedRoute requiredPermission="analytics:read"><Analytics /></ProtectedRoute>} />
                  <Route path="/threat-intelligence" element={<ProtectedRoute requiredPermission="threat_intel:read"><ThreatIntelligence /></ProtectedRoute>} />
                  <Route path="/incidents" element={<ProtectedRoute requiredPermission="incidents:read"><IncidentManager /></ProtectedRoute>} />
                  <Route path="/notification-settings" element={<ProtectedRoute requiredPermission="notifications:test"><NotificationSettings /></ProtectedRoute>} />
                  <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
                  <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                  <Route path="/testing" element={<ProtectedRoute requiredPermission="predict:execute"><AttackSimulation /></ProtectedRoute>} />
                  <Route path="/models" element={<ProtectedRoute><Models /></ProtectedRoute>} />
                  <Route path="/users" element={<ProtectedRoute requiredPermission="users:read"><UserManagement /></ProtectedRoute>} />
                  <Route path="/audit" element={<ProtectedRoute requiredPermission="audit:read"><AuditLog /></ProtectedRoute>} />
                </Route>
              </Routes>
            </WebSocketProvider>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
