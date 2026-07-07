import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusBadge, Badge } from "@/components/ui/Badge";
import { Table, type Column } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { Tabs } from "@/components/ui/Tabs";
import apiClient from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { Assessment } from "@/types/assessment";
import type { PaginatedResponse } from "@/types/api";

const columns: Column<Assessment>[] = [
  { key: "title", header: "Title", render: (a) => (
    <span className="font-medium text-surface-900 dark:text-surface-100">{a.title}</span>
  )},
  { key: "status", header: "Status", render: (a) => <StatusBadge status={a.status} /> },
  { key: "score", header: "Score", render: (a) => (
    <span className={a.score !== null ? "font-medium" : "text-surface-400"}>
      {a.score !== null ? `${a.score}%` : "-"}
    </span>
  )},
  { key: "due_date", header: "Due Date", render: (a) => (
    <span className="text-sm text-surface-500">{formatDate(a.due_date)}</span>
  ), className: "hidden md:table-cell" },
  { key: "findings", header: "Findings", render: (a) => (
    <Badge variant={a.findings.length > 0 ? "warning" : "default"} size="sm">
      {a.findings.length}
    </Badge>
  ), className: "hidden lg:table-cell" },
];

export function AssessmentsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [activeTab, setActiveTab] = useState("all");
  const pageSize = 20;

  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (activeTab !== "all") params.status = activeTab;

  const { data, isLoading } = useQuery({
    queryKey: ["assessments", page, activeTab],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Assessment>>("/assessments", { params });
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            Assessments
          </h1>
          <p className="text-surface-500 dark:text-surface-400">
            Manage compliance assessments and findings
          </p>
        </div>
        <Button onClick={() => navigate("/assessments/new")} leftIcon={<Plus className="h-4 w-4" />}>
          New Assessment
        </Button>
      </div>

      <Card padding="none">
        <div className="border-b border-surface-200 px-6 pt-4 dark:border-surface-700">
          <Tabs
            tabs={[
              { id: "all", label: "All" },
              { id: "scheduled", label: "Scheduled" },
              { id: "in_progress", label: "In Progress" },
              { id: "completed", label: "Completed" },
              { id: "approved", label: "Approved" },
            ]}
            activeTab={activeTab}
            onTabChange={(tab) => { setActiveTab(tab); setPage(1); }}
          />
        </div>

        <Table
          columns={columns}
          data={data?.items || []}
          keyExtractor={(a) => a.id}
          onRowClick={(a) => navigate(`/assessments/${a.id}`)}
          isLoading={isLoading}
          emptyMessage="No assessments found"
        />

        {data && (
          <div className="border-t border-surface-200 px-6 py-4 dark:border-surface-700">
            <Pagination
              page={page}
              totalPages={data.total_pages}
              onPageChange={setPage}
            />
          </div>
        )}
      </Card>
    </div>
  );
}
