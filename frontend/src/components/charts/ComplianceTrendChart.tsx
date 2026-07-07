import {
  AreaChart,
  Area,
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
  date: string;
  compliance: number;
  target?: number;
}

interface ComplianceTrendChartProps {
  data: DataPoint[];
  title?: string;
  className?: string;
}

export function ComplianceTrendChart({
  data,
  title = "Compliance Trend",
  className,
}: ComplianceTrendChartProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="complianceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-surface-200 dark:stroke-surface-700" />
            <XAxis
              dataKey="date"
              className="text-xs text-surface-500"
              tick={{ fill: "currentColor" }}
              tickLine={false}
            />
            <YAxis
              className="text-xs text-surface-500"
              tick={{ fill: "currentColor" }}
              tickLine={false}
              axisLine={false}
              domain={[0, 100]}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--tooltip-bg, #fff)",
                border: "1px solid var(--tooltip-border, #e2e8f0)",
                borderRadius: "8px",
                fontSize: "13px",
              }}
              formatter={(value: number) => [`${value.toFixed(1)}%`]}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="compliance"
              stroke="#6366f1"
              strokeWidth={2}
              fill="url(#complianceGradient)"
              name="Compliance Rate"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
            {data[0]?.target !== undefined && (
              <Area
                type="monotone"
                dataKey="target"
                stroke="#10b981"
                strokeWidth={2}
                strokeDasharray="5 5"
                fill="none"
                name="Target"
                dot={false}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
