export interface MetricCard {
  id: string;
  label: string;
  value: number;
  previous_value: number;
  change_percentage: number;
  trend: "up" | "down" | "neutral";
  icon: string;
}

export interface ChartDataPoint {
  date: string;
  value: number;
  previous_value?: number;
  category?: string;
}

export interface RiskDistribution {
  category: string;
  count: number;
  percentage: number;
  risk_level: string;
}

export interface ActivityEvent {
  id: string;
  type: string;
  description: string;
  user_name: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface DashboardOverview {
  metrics: MetricCard[];
  recent_activity: ActivityEvent[];
  compliance_rate: number;
  open_findings: number;
  active_regulations: number;
  entities_monitored: number;
}

export interface CoverageData {
  name: string;
  covered: number;
  total: number;
}
