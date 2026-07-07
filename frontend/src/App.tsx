import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "react-redux";
import { Toaster } from "react-hot-toast";
import { Suspense, lazy } from "react";
import { store } from "@/app/store";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGuard } from "@/features/auth/AuthGuard";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { UsersPage } from "@/features/admin/UsersPage";
import { UserDetailPage } from "@/features/admin/UserDetailPage";
import { RolesPage } from "@/features/admin/RolesPage";
import { RegulationsPage } from "@/features/regulations/RegulationsPage";
import { AssessmentsPage } from "@/features/assessments/AssessmentsPage";
import { EntitiesPage } from "@/features/entities/EntitiesPage";
import { DocumentsPage } from "@/features/documents/DocumentsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { NotFoundPage } from "@/features/errors/NotFoundPage";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { PageSpinner } from "@/components/ui/Spinner";
import { useCurrentUser } from "@/hooks/useAuth";
import { setStoreRef } from "@/lib/api-client";

const KnowledgeGraphPage = lazy(() => import("@/features/regulations/KnowledgeGraphPage").then(m => ({ default: m.KnowledgeGraphPage })));

setStoreRef(store);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppContent() {
  const { isLoading } = useCurrentUser();

  if (isLoading) return <PageSpinner />;

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          element={
            <AuthGuard>
              <AppShell />
            </AuthGuard>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/regulations" element={<RegulationsPage />} />
          <Route path="/knowledge-graph" element={
            <Suspense fallback={<PageSpinner />}>
              <KnowledgeGraphPage />
            </Suspense>
          } />
          <Route path="/assessments" element={<AssessmentsPage />} />
          <Route path="/entities" element={<EntitiesPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/admin/users" element={<AuthGuard requireAdmin><UsersPage /></AuthGuard>} />
          <Route path="/admin/users/:userId" element={<AuthGuard requireAdmin><UserDetailPage /></AuthGuard>} />
          <Route path="/admin/roles" element={<AuthGuard requireAdmin><RolesPage /></AuthGuard>} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}

export default function App() {
  return (
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppContent />
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                borderRadius: "12px",
                background: "var(--toast-bg, #fff)",
                color: "var(--toast-color, #0f172a)",
                border: "1px solid var(--toast-border, #e2e8f0)",
                fontSize: "14px",
              },
            }}
          />
        </BrowserRouter>
      </QueryClientProvider>
    </Provider>
  );
}
