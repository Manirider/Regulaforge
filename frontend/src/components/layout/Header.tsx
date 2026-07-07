import {
  Menu,
  Moon,
  Sun,
  Bell,
  LogOut,
  User,
  ChevronDown,
  Search,
} from "lucide-react";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { toggleSidebar } from "@/stores/uiSlice";
import { useLogout } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { Dropdown } from "@/components/ui/Dropdown";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { useState } from "react";

export function Header() {
  const dispatch = useAppDispatch();
  const { user } = useAppSelector((s) => s.auth);
  const { isDark, toggle: toggleTheme } = useTheme();
  const logout = useLogout();
  const [searchOpen] = useState(false);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-surface-200 bg-white/80 px-4 backdrop-blur-sm dark:border-surface-700 dark:bg-surface-900/80">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => dispatch(toggleSidebar())}
        className="lg:hidden"
        aria-label="Toggle sidebar"
      >
        <Menu className="h-5 w-5" />
      </Button>

      <div
        className={cn(
          "hidden flex-1 items-center md:flex",
          searchOpen && "flex",
        )}
      >
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <input
            type="search"
            placeholder="Search regulations, entities..."
            className="w-full rounded-lg border border-surface-300 bg-surface-50 py-2 pl-10 pr-4 text-sm text-surface-900 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100 dark:placeholder-surface-500"
            aria-label="Global search"
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleTheme}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        <Button
          variant="ghost"
          size="sm"
          className="relative"
          aria-label="Notifications"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" />
        </Button>

        <Dropdown
          trigger={
            <div className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-surface-50 dark:hover:bg-surface-800">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 dark:bg-brand-900 dark:text-brand-300">
                {user?.full_name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || "U"}
              </div>
              <div className="hidden text-left md:block">
                <p className="text-sm font-medium text-surface-900 dark:text-surface-100">
                  {user?.full_name || user?.username || "User"}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400">
                  {user?.email}
                </p>
              </div>
              <ChevronDown className="hidden h-4 w-4 text-surface-400 md:block" />
            </div>
          }
          items={[
            {
              label: "Profile",
              onClick: () => {},
              icon: <User className="h-4 w-4" />,
            },
            {
              label: "Sign out",
              onClick: logout,
              icon: <LogOut className="h-4 w-4" />,
              danger: true,
            },
          ]}
        />
      </div>
    </header>
  );
}
