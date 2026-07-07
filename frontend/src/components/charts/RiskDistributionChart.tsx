import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface RiskItem {
  name: string;
  value: number;
  color: string;
}

interface RiskDistributionChartProps {
  data: RiskItem[];
  title?: string;
  className?: string;
}

const DEFAULT_COLORS = {
  low: "#22c55e",
  medium: "#eab308",
  high: "#f97316",
  critical: "#ef4444",
};

export function RiskDistributionChart({
  data,
  title = "Risk Distribution",
  className,
}: RiskDistributionChartProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
              label={({ name, percent }) =>
                `${name} ${(percent * 100).toFixed(0)}%`
              }
              labelLine={false}
            >
              {data.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={entry.color || DEFAULT_COLORS[entry.name as keyof typeof DEFAULT_COLORS] || "#6366f1"}
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [value, "Findings"]}
              contentStyle={{
                backgroundColor: "var(--tooltip-bg, #fff)",
                border: "1px solid var(--tooltip-border, #e2e8f0)",
                borderRadius: "8px",
                fontSize: "13px",
              }}
            />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
