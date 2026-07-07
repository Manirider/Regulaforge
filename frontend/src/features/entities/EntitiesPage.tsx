import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, Building2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusBadge, Badge } from "@/components/ui/Badge";
import { Table, type Column } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import apiClient from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { Entity } from "@/types/entity";
import type { PaginatedResponse } from "@/types/api";

const entityTypeLabels: Record<string, string> = {
  organization: "Organization",
  department: "Department",
  subsidiary: "Subsidiary",
  project: "Project",
  system: "System",
  third_party: "Third Party",
  other: "Other",
};

const columns: Column<Entity>[] = [
  { key: "name", header: "Name", render: (e) => (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-950/30 dark:text-brand-400">
        <Building2 className="h-4 w-4" />
      </div>
      <div>
        <p className="font-medium text-surface-900 dark:text-surface-100">{e.name}</p>
        <p className="text-xs text-surface-500">{entityTypeLabels[e.entity_type]}</p>
      </div>
    </div>
  )},
  { key: "entity_type", header: "Type", render: (e) => (
    <Badge variant="default" size="sm">{entityTypeLabels[e.entity_type]}</Badge>
  ), className: "hidden md:table-cell" },
  { key: "is_active", header: "Status", render: (e) => (
    <StatusBadge status={e.is_active ? "active" : "inactive"} />
  )},
  { key: "created_at", header: "Created", render: (e) => (
    <span className="text-sm text-surface-500">{formatDate(e.created_at)}</span>
  ), className: "hidden lg:table-cell" },
];

export function EntitiesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["entities", page],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Entity>>("/entities", {
        params: { page, page_size: pageSize },
      });
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            Entities
          </h1>
          <p className="text-surface-500 dark:text-surface-400">
            Manage monitored entities and organizational units
          </p>
        </div>
        <Button onClick={() => navigate("/entities/new")} leftIcon={<Plus className="h-4 w-4" />}>
          Add Entity
        </Button>
      </div>

      <Card padding="none">
        <Table
          columns={columns}
          data={data?.items || []}
          keyExtractor={(e) => e.id}
          onRowClick={(e) => navigate(`/entities/${e.id}`)}
          isLoading={isLoading}
          emptyMessage="No entities found"
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
