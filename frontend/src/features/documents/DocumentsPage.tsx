import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, FileText } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusBadge, Badge } from "@/components/ui/Badge";
import { Table, type Column } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { Tabs } from "@/components/ui/Tabs";
import apiClient from "@/lib/api-client";
import { formatDate, formatBytes } from "@/lib/utils";
import type { Document } from "@/types/document";
import type { PaginatedResponse } from "@/types/api";

const columns: Column<Document>[] = [
  { key: "title", header: "Title", render: (d) => (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400">
        <FileText className="h-4 w-4" />
      </div>
      <div>
        <p className="font-medium text-surface-900 dark:text-surface-100">{d.title}</p>
        <p className="text-xs text-surface-500">{d.artifact_type}</p>
      </div>
    </div>
  )},
  { key: "processing_status", header: "Status", render: (d) => (
    <StatusBadge status={d.processing_status} />
  )},
  { key: "is_verified", header: "Verified", render: (d) => (
    d.is_verified ? <Badge variant="success">Verified</Badge> : <Badge variant="warning">Pending</Badge>
  )},
  { key: "file_size", header: "Size", render: (d) => (
    <span className="text-sm text-surface-500">{formatBytes(d.file_size)}</span>
  ), className: "hidden md:table-cell" },
  { key: "created_at", header: "Uploaded", render: (d) => (
    <span className="text-sm text-surface-500">{formatDate(d.created_at)}</span>
  ), className: "hidden lg:table-cell" },
];

export function DocumentsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [activeTab, setActiveTab] = useState("all");
  const pageSize = 20;

  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (activeTab !== "all") params.processing_status = activeTab;

  const { data, isLoading } = useQuery({
    queryKey: ["documents", page, activeTab],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Document>>("/documents", { params });
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            Documents
          </h1>
          <p className="text-surface-500 dark:text-surface-400">
            Upload and manage compliance documents
          </p>
        </div>
        <Button onClick={() => navigate("/documents/upload")} leftIcon={<Plus className="h-4 w-4" />}>
          Upload Document
        </Button>
      </div>

      <Card padding="none">
        <div className="border-b border-surface-200 px-6 pt-4 dark:border-surface-700">
          <Tabs
            tabs={[
              { id: "all", label: "All" },
              { id: "completed", label: "Completed" },
              { id: "processing", label: "Processing" },
              { id: "pending", label: "Pending" },
              { id: "failed", label: "Failed" },
            ]}
            activeTab={activeTab}
            onTabChange={(tab) => { setActiveTab(tab); setPage(1); }}
          />
        </div>

        <Table
          columns={columns}
          data={data?.items || []}
          keyExtractor={(d) => d.id}
          onRowClick={(d) => navigate(`/documents/${d.id}`)}
          isLoading={isLoading}
          emptyMessage="No documents found"
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
