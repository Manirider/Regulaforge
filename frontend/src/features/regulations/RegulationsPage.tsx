import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusBadge, Badge } from "@/components/ui/Badge";
import { Table, type Column } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { Tabs } from "@/components/ui/Tabs";
import apiClient from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { Regulation } from "@/types/regulation";
import type { PaginatedResponse } from "@/types/api";

const categoryLabels: Record<string, string> = {
  data_protection: "Data Protection",
  financial: "Financial",
  environmental: "Environmental",
  health_safety: "Health & Safety",
  corporate_governance: "Corporate Governance",
  trade_compliance: "Trade Compliance",
  employment: "Employment",
  anti_money_laundering: "Anti-Money Laundering",
  cybersecurity: "Cybersecurity",
  other: "Other",
};

const columns: Column<Regulation>[] = [
  { key: "code", header: "Code", render: (r) => (
    <span className="font-mono text-sm font-medium text-brand-600 dark:text-brand-400">{r.code}</span>
  )},
  { key: "title", header: "Title", render: (r) => (
    <div>
      <p className="font-medium text-surface-900 dark:text-surface-100">{r.title}</p>
      <p className="text-xs text-surface-500">{r.issuing_body}</p>
    </div>
  )},
  { key: "category", header: "Category", render: (r) => (
    <Badge variant="default" size="sm">{categoryLabels[r.category] || r.category}</Badge>
  ), className: "hidden lg:table-cell" },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "effective_date", header: "Effective", render: (r) => (
    <span className="text-sm text-surface-500">{formatDate(r.effective_date)}</span>
  ), className: "hidden md:table-cell" },
  { key: "version", header: "Ver.", render: (r) => (
    <span className="text-sm text-surface-500">v{r.version}</span>
  ), className: "hidden md:table-cell" },
];

export function RegulationsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [activeTab, setActiveTab] = useState("all");
  const pageSize = 20;

  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (search) params.search = search;
  if (statusFilter) params.status = statusFilter;

  const { data, isLoading } = useQuery({
    queryKey: ["regulations", page, search, statusFilter],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Regulation>>("/regulations", { params });
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            Regulations
          </h1>
          <p className="text-surface-500 dark:text-surface-400">
            Browse and manage regulatory requirements
          </p>
        </div>
        <Button onClick={() => navigate("/regulations/new")} leftIcon={<Plus className="h-4 w-4" />}>
          Add Regulation
        </Button>
      </div>

      <Card padding="none">
        <div className="border-b border-surface-200 px-6 pt-4 dark:border-surface-700">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <Tabs
              tabs={[
                { id: "all", label: "All" },
                { id: "active", label: "Active" },
                { id: "draft", label: "Draft" },
                { id: "repealed", label: "Repealed" },
              ]}
              activeTab={activeTab}
              onTabChange={(tab) => { setActiveTab(tab); setStatusFilter(tab === "all" ? "" : tab); setPage(1); }}
            />
            <div className="flex gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
                <input
                  type="search"
                  placeholder="Search regulations..."
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                  className="w-48 rounded-lg border border-surface-300 bg-surface-50 py-2 pl-10 pr-4 text-sm dark:border-surface-600 dark:bg-surface-800 lg:w-64"
                  aria-label="Search regulations"
                />
              </div>
            </div>
          </div>
        </div>

        <Table
          columns={columns}
          data={data?.items || []}
          keyExtractor={(r) => r.id}
          onRowClick={(r) => navigate(`/regulations/${r.id}`)}
          isLoading={isLoading}
          emptyMessage="No regulations found"
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
