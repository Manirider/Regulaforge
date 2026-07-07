import { Navigate, useLocation } from "react-router-dom";
import { useAppSelector } from "@/app/hooks";
import { PageSpinner } from "@/components/ui/Spinner";

interface AuthGuardProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

export function AuthGuard({ children, requireAdmin }: AuthGuardProps) {
  const { isAuthenticated, isLoading, user } = useAppSelector((s) => s.auth);
  const location = useLocation();

  if (isLoading) {
    return <PageSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireAdmin && user && !user.is_superuser) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
