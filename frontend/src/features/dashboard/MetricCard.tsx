import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;
  trend?: "up" | "down" | "neutral";
  icon?: React.ReactNode;
  className?: string;
}

export function MetricCard({
  label,
  value,
  change,
  trend,
  icon,
  className,
}: MetricCardProps) {
  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-surface-500 dark:text-surface-400">
            {label}
          </p>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            {value}
          </p>
          {change !== undefined && (
            <div className="flex items-center gap-1">
              {trend === "up" && (
                <ArrowUpRight className="h-4 w-4 text-green-500" />
              )}
              {trend === "down" && (
                <ArrowDownRight className="h-4 w-4 text-red-500" />
              )}
              {trend === "neutral" && (
                <Minus className="h-4 w-4 text-surface-400" />
              )}
              <span
                className={cn(
                  "text-sm font-medium",
                  trend === "up" && "text-green-600 dark:text-green-400",
                  trend === "down" && "text-red-600 dark:text-red-400",
                  trend === "neutral" && "text-surface-500",
                )}
              >
                {change > 0 && "+"}
                {change}%
              </span>
              <span className="text-xs text-surface-400">vs last month</span>
            </div>
          )}
        </div>
        {icon && (
          <div className="rounded-lg bg-brand-50 p-2.5 text-brand-600 dark:bg-brand-950/30 dark:text-brand-400">
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}
