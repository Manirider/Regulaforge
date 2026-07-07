import { Link, useLocation } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";
import { cn } from "@/lib/utils";

const routeLabels: Record<string, string> = {
  dashboard: "Dashboard",
  regulations: "Regulations",
  assessments: "Assessments",
  entities: "Entities",
  documents: "Documents",
  analytics: "Analytics",
  "knowledge-graph": "Knowledge Graph",
  admin: "Admin",
  users: "Users",
  roles: "Roles",
  settings: "Settings",
};

export function Breadcrumb({ className }: { className?: string }) {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn("flex items-center gap-1 text-sm text-surface-500 dark:text-surface-400", className)}
    >
      <Link
        to="/dashboard"
        className="hover:text-surface-700 dark:hover:text-surface-300"
        aria-label="Home"
      >
        <Home className="h-4 w-4" />
      </Link>

      {segments.map((segment, index) => {
        const path = "/" + segments.slice(0, index + 1).join("/");
        const label = routeLabels[segment] || segment.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        const isLast = index === segments.length - 1;

        return (
          <span key={path} className="flex items-center gap-1">
            <ChevronRight className="h-3.5 w-3.5" />
            {isLast ? (
              <span className="font-medium text-surface-900 dark:text-surface-100" aria-current="page">
                {label}
              </span>
            ) : (
              <Link
                to={path}
                className="hover:text-surface-700 dark:hover:text-surface-300"
              >
                {label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
