import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Shield } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { PageSpinner } from "@/components/ui/Spinner";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import apiClient, { getErrorMessage } from "@/lib/api-client";
import type { Role, CreateRoleRequest } from "@/types/admin";
import toast from "react-hot-toast";

export function RolesPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [form, setForm] = useState<CreateRoleRequest>({
    name: "",
    description: "",
    permissions: [],
  });

  const { data: roles, isLoading } = useQuery({
    queryKey: ["admin-roles"],
    queryFn: async () => {
      const { data } = await apiClient.get<Role[]>("/admin/roles");
      return data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (payload: CreateRoleRequest) => {
      const { data } = await apiClient.post("/admin/roles", payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-roles"] });
      toast.success("Role created");
      setShowCreateModal(false);
      setForm({ name: "", description: "", permissions: [] });
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  if (isLoading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            Role Management
          </h1>
          <p className="text-surface-500 dark:text-surface-400">
            Define roles and their permissions
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} leftIcon={<Plus className="h-4 w-4" />}>
          Create Role
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {roles?.map((role) => (
          <Card key={role.id}>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-brand-600 dark:text-brand-400" />
                  <h3 className="font-semibold text-surface-900 dark:text-surface-100">
                    {role.name}
                  </h3>
                </div>
                {role.description && (
                  <p className="mt-1 text-sm text-surface-500">{role.description}</p>
                )}
              </div>
              {role.is_system_role && (
                <Badge variant="info">System</Badge>
              )}
            </div>
            {role.permissions.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {role.permissions.map((perm) => (
                  <Badge key={perm} variant="default" size="sm">
                    {perm}
                  </Badge>
                ))}
              </div>
            )}
          </Card>
        ))}
        {(!roles || roles.length === 0) && (
          <p className="col-span-full py-12 text-center text-surface-500">
            No roles defined yet
          </p>
        )}
      </div>

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create Role"
      >
        <div className="space-y-4">
          <Input
            label="Name"
            placeholder="e.g., compliance_officer"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input
            label="Description"
            placeholder="Brief description of the role"
            value={form.description || ""}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowCreateModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => createMutation.mutate(form)}
              disabled={!form.name}
              isLoading={createMutation.isPending}
            >
              Create
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
