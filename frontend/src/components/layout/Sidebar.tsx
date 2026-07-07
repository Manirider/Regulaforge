import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Shield,
  ClipboardCheck,
  Building2,
  FileText,
  Users,
  Settings,
  BarChart3,
  Network,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import {
  toggleSidebarCollapsed,
  setSidebarOpen,
} from "@/stores/uiSlice";
import { Button } from "@/components/ui/Button";

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  roles?: string[];
}

const navItems: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: <LayoutDashboard className="h-5 w-5" /> },
  { label: "Regulations", path: "/regulations", icon: <Shield className="h-5 w-5" /> },
  { label: "Assessments", path: "/assessments", icon: <ClipboardCheck className="h-5 w-5" /> },
  { label: "Entities", path: "/entities", icon: <Building2 className="h-5 w-5" /> },
  { label: "Documents", path: "/documents", icon: <FileText className="h-5 w-5" /> },
  { label: "Analytics", path: "/analytics", icon: <BarChart3 className="h-5 w-5" /> },
  { label: "Knowledge Graph", path: "/knowledge-graph", icon: <Network className="h-5 w-5" /> },
  { label: "Admin", path: "/admin/users", icon: <Users className="h-5 w-5" />, roles: ["admin"] },
  { label: "Settings", path: "/settings", icon: <Settings className="h-5 w-5" /> },
];

export function Sidebar() {
  const dispatch = useAppDispatch();
  const { sidebarCollapsed, sidebarOpen } = useAppSelector((s) => s.ui);
  const location = useLocation();

  function isActive(path: string) {
    if (path === "/dashboard") return location.pathname === "/dashboard";
    return location.pathname.startsWith(path);
  }

  return (
    <>
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => dispatch(setSidebarOpen(false))}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed left-0 top-0 z-50 flex h-full flex-col border-r border-surface-200 bg-white transition-all duration-300 dark:border-surface-700 dark:bg-surface-900 lg:static lg:z-auto",
          sidebarCollapsed ? "w-[68px]" : "w-64",
          sidebarOpen
            ? "translate-x-0"
            : "-translate-x-full lg:translate-x-0",
        )}
        aria-label="Sidebar navigation"
      >
        <div
          className={cn(
            "flex h-16 items-center border-b border-surface-200 px-4 dark:border-surface-700",
            sidebarCollapsed ? "justify-center" : "justify-between",
          )}
        >
          {!sidebarCollapsed && (
            <span className="text-xl font-bold text-brand-600 dark:text-brand-400">
              RegulaForge
            </span>
          )}
          {sidebarCollapsed && (
            <span className="text-xl font-bold text-brand-600 dark:text-brand-400">
              RF
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => dispatch(toggleSidebarCollapsed())}
            className="hidden lg:flex"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => dispatch(setSidebarOpen(false))}
            className="lg:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => dispatch(setSidebarOpen(false))}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive(item.path)
                  ? "bg-brand-50 text-brand-700 dark:bg-brand-950/30 dark:text-brand-400"
                  : "text-surface-600 hover:bg-surface-50 hover:text-surface-900 dark:text-surface-400 dark:hover:bg-surface-800 dark:hover:text-surface-200",
                sidebarCollapsed && "justify-center px-2",
              )}
              title={sidebarCollapsed ? item.label : undefined}
              aria-label={sidebarCollapsed ? item.label : undefined}
            >
              {item.icon}
              {!sidebarCollapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-surface-200 p-3 dark:border-surface-700">
          <div
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2",
              sidebarCollapsed && "justify-center",
            )}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 dark:bg-brand-900 dark:text-brand-300">
              RF
            </div>
            {!sidebarCollapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-surface-900 dark:text-surface-100">
                  RegulaForge
                </p>
                <p className="truncate text-xs text-surface-500 dark:text-surface-400">
                  v0.1.0
                </p>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
