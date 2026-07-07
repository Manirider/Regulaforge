import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info";
  className?: string;
  size?: "sm" | "md";
}

const variants = {
  default:
    "bg-surface-100 text-surface-700 dark:bg-surface-700 dark:text-surface-300",
  success:
    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  warning:
    "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  danger: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  info: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
};

const sizes = {
  sm: "px-1.5 py-0.5 text-xs",
  md: "px-2.5 py-1 text-sm",
};

export function Badge({
  children,
  variant = "default",
  className,
  size = "sm",
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-medium",
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const variantMap: Record<string, BadgeProps["variant"]> = {
    active: "success",
    draft: "warning",
    completed: "info",
    approved: "success",
    in_progress: "info",
    pending: "default",
    failed: "danger",
    cancelled: "default",
    repealed: "danger",
    superseded: "warning",
    low: "success",
    medium: "warning",
    high: "danger",
    critical: "danger",
  };

  return (
    <Badge variant={variantMap[status] || "default"} className={className}>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}
