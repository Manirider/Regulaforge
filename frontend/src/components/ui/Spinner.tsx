import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const sizes = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-10 w-10",
};

export function Spinner({ size = "md", className, label }: SpinnerProps) {
  return (
    <div
      className={cn("flex items-center justify-center gap-2", className)}
      role="status"
    >
      <Loader2 className={cn("animate-spin text-brand-600 dark:text-brand-400", sizes[size])} />
      {label && (
        <span className="text-sm text-surface-500 dark:text-surface-400">
          {label}
        </span>
      )}
      <span className="sr-only">Loading{label ? `: ${label}` : ""}...</span>
    </div>
  );
}

export function PageSpinner() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <Spinner size="lg" label="Loading..." />
    </div>
  );
}
