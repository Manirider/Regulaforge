import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface DataPoint {
  month: string;
  open: number;
  closed: number;
}

interface FindingsTrendChartProps {
  data: DataPoint[];
  title?: string;
  className?: string;
}

export function FindingsTrendChart({
  data,
  title = "Findings Trend",
  className,
}: FindingsTrendChartProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-surface-200 dark:stroke-surface-700" />
            <XAxis
              dataKey="month"
              className="text-xs text-surface-500"
              tick={{ fill: "currentColor" }}
              tickLine={false}
            />
            <YAxis
              className="text-xs text-surface-500"
              tick={{ fill: "currentColor" }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--tooltip-bg, #fff)",
                border: "1px solid var(--tooltip-border, #e2e8f0)",
                borderRadius: "8px",
                fontSize: "13px",
              }}
            />
            <Legend />
            <Bar
              dataKey="open"
              fill="#f97316"
              radius={[4, 4, 0, 0]}
              name="Open"
              maxBarSize={40}
            />
            <Bar
              dataKey="closed"
              fill="#22c55e"
              radius={[4, 4, 0, 0]}
              name="Closed"
              maxBarSize={40}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
