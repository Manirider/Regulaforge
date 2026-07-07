import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Shield, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Table, type Column } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";

import { Tabs } from "@/components/ui/Tabs";
import apiClient from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import type { User } from "@/types/auth";
import type { PaginatedResponse } from "@/types/api";


const columns: Column<User>[] = [
  { key: "full_name", header: "Name", render: (u) => (
    <div>
      <p className="font-medium text-surface-900 dark:text-surface-100">
        {u.full_name || u.username}
      </p>
      <p className="text-xs text-surface-500">{u.email}</p>
    </div>
  )},
  { key: "username", header: "Username", className: "hidden md:table-cell" },
  { key: "is_active", header: "Status", render: (u) => (
    <StatusBadge status={u.is_active ? "active" : "inactive"} />
  )},
  { key: "is_superuser", header: "Role", render: (u) => (
    u.is_superuser ? <Badge variant="info">Admin</Badge> : <Badge>User</Badge>
  )},
  { key: "last_login_at", header: "Last Login", render: (u) => (
    <span className="text-surface-500">{u.last_login_at ? formatDateTime(u.last_login_at) : "Never"}</span>
  ), className: "hidden lg:table-cell" },
];

export function UsersPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("all");
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page, search, activeTab],
    queryFn: async () => {
      const params: Record<string, string | number> = { page, page_size: pageSize };
      if (search) params.email = search;
      if (activeTab === "active") params.is_active = "true";
      if (activeTab === "inactive") params.is_active = "false";
      const { data } = await apiClient.get<PaginatedResponse<User>>("/admin/users", { params });
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            User Management
          </h1>
          <p className="text-surface-500 dark:text-surface-400">
            Manage users and their access permissions
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate("/admin/roles")} leftIcon={<Shield className="h-4 w-4" />}>
            Roles
          </Button>
        </div>
      </div>

      <Card padding="none">
        <div className="border-b border-surface-200 px-6 pt-4 dark:border-surface-700">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <Tabs
              tabs={[
                { id: "all", label: "All Users" },
                { id: "active", label: "Active" },
                { id: "inactive", label: "Inactive" },
              ]}
              activeTab={activeTab}
              onTabChange={setActiveTab}
            />
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
              <input
                type="search"
                placeholder="Search by email..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="w-full rounded-lg border border-surface-300 bg-surface-50 py-2 pl-10 pr-4 text-sm dark:border-surface-600 dark:bg-surface-800"
                aria-label="Search users"
              />
            </div>
          </div>
        </div>

        <Table
          columns={columns}
          data={data?.items || []}
          keyExtractor={(u) => u.id}
          onRowClick={(u) => navigate(`/admin/users/${u.id}`)}
          isLoading={isLoading}
          emptyMessage="No users found"
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
