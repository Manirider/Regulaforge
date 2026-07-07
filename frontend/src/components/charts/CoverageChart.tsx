import {
  RadialBarChart,
  RadialBar,
  ResponsiveContainer,
  Legend,
  PolarAngleAxis,
} from "recharts";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface CoverageItem {
  name: string;
  value: number;
  fill: string;
}

interface CoverageChartProps {
  data: CoverageItem[];
  title?: string;
  className?: string;
}

export function CoverageChart({
  data,
  title = "Regulatory Coverage",
  className,
}: CoverageChartProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="20%"
            outerRadius="90%"
            barSize={16}
            data={data}
            startAngle={180}
            endAngle={-180}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
            <RadialBar
              background
              dataKey="value"
              cornerRadius={8}
              label={{
                position: "insideStart",
                fill: "currentColor",
                fontSize: 11,
              }}
            />
            <Legend
              iconType="circle"
              formatter={(value: string) => (
                <span className="text-sm text-surface-600 dark:text-surface-400">{value}</span>
              )}
            />
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
