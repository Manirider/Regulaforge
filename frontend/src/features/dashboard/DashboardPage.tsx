import {
  Shield,
  ClipboardCheck,
  Building2,
  AlertTriangle,
  FileText,
} from "lucide-react";
import { MetricCard } from "./MetricCard";
import { ActivityFeed } from "./ActivityFeed";
import { ComplianceTrendChart } from "@/components/charts/ComplianceTrendChart";
import { RiskDistributionChart } from "@/components/charts/RiskDistributionChart";
import { FindingsTrendChart } from "@/components/charts/FindingsTrendChart";
import { CoverageChart } from "@/components/charts/CoverageChart";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useNavigate } from "react-router-dom";
import {
  useDashboardOverview,
  useComplianceTrend,
  useRiskDistribution,
  useFindingsTrend,
  useCoverage,
} from "@/hooks/useDashboard";

export function DashboardPage() {
  const navigate = useNavigate();
  const { data: overview, isFetching } = useDashboardOverview();
  const { data: complianceTrend } = useComplianceTrend();
  const { data: riskDistribution } = useRiskDistribution();
  const { data: findingsTrend } = useFindingsTrend();
  const { data: coverageData } = useCoverage();

  const activities = overview?.recent_activity ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            Dashboard
          </h1>
          <p className="text-surface-500 dark:text-surface-400">
            Welcome back. Here&apos;s your compliance overview.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isFetching && <Spinner size="sm" />}
          <Button variant="outline" onClick={() => navigate("/assessments")}>
            View Assessments
          </Button>
          <Button onClick={() => navigate("/regulations")}>
            Browse Regulations
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Compliance Rate"
          value={`${overview?.compliance_rate ?? 94}%`}
          change={3.3}
          trend="up"
          icon={<Shield className="h-5 w-5" />}
        />
        <MetricCard
          label="Open Findings"
          value={overview?.open_findings ?? 23}
          change={-17.9}
          trend="down"
          icon={<AlertTriangle className="h-5 w-5" />}
        />
        <MetricCard
          label="Active Regulations"
          value={overview?.active_regulations ?? 156}
          change={5.4}
          trend="up"
          icon={<ClipboardCheck className="h-5 w-5" />}
        />
        <MetricCard
          label="Entities Monitored"
          value={overview?.entities_monitored ?? 48}
          change={6.7}
          trend="up"
          icon={<Building2 className="h-5 w-5" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ComplianceTrendChart data={complianceTrend ?? []} />
        <RiskDistributionChart data={riskDistribution ?? []} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <FindingsTrendChart data={findingsTrend ?? []} className="lg:col-span-2" />
        <CoverageChart data={coverageData ?? []} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <ActivityFeed
          activities={activities}
          className="lg:col-span-2"
        />
        <Card className="p-6">
          <h3 className="mb-4 text-lg font-semibold text-surface-900 dark:text-surface-100">
            Quick Actions
          </h3>
          <div className="space-y-3">
            <Button
              variant="outline"
              className="w-full justify-start"
              leftIcon={<ClipboardCheck className="h-4 w-4" />}
              onClick={() => navigate("/assessments/new")}
            >
              New Assessment
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              leftIcon={<Shield className="h-4 w-4" />}
              onClick={() => navigate("/regulations/new")}
            >
              Add Regulation
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              leftIcon={<Building2 className="h-4 w-4" />}
              onClick={() => navigate("/entities/new")}
            >
              Register Entity
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              leftIcon={<FileText className="h-4 w-4" />}
              onClick={() => navigate("/documents/upload")}
            >
              Upload Document
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
