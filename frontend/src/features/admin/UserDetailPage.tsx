import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  UserCheck,
  UserX,
  Shield,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { PageSpinner } from "@/components/ui/Spinner";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import apiClient, { getErrorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import type { User } from "@/types/auth";
import type { Role } from "@/types/admin";
import toast from "react-hot-toast";

export function UserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [selectedRole, setSelectedRole] = useState("");

  const { data: user, isLoading } = useQuery({
    queryKey: ["admin-user", userId],
    queryFn: async () => {
      const { data } = await apiClient.get<User>(`/admin/users/${userId}`);
      return data;
    },
    enabled: !!userId,
  });

  const { data: roles } = useQuery({
    queryKey: ["admin-roles"],
    queryFn: async () => {
      const { data } = await apiClient.get<Role[]>("/admin/roles");
      return data;
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: () => apiClient.post(`/admin/users/${userId}/deactivate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-user", userId] });
      toast.success("User deactivated");
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  const activateMutation = useMutation({
    mutationFn: () => apiClient.post(`/admin/users/${userId}/activate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-user", userId] });
      toast.success("User activated");
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  const assignRoleMutation = useMutation({
    mutationFn: (roleId: string) =>
      apiClient.post(`/admin/users/${userId}/roles/${roleId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-user", userId] });
      toast.success("Role assigned");
      setShowRoleModal(false);
      setSelectedRole("");
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  if (isLoading) return <PageSpinner />;
  if (!user) return <div className="py-12 text-center text-surface-500">User not found</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/admin/users")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
            {user.full_name || user.username}
          </h1>
          <p className="text-surface-500 dark:text-surface-400">{user.email}</p>
        </div>
        <div className="ml-auto flex gap-2">
          {user.is_active ? (
            <Button
              variant="danger"
              size="sm"
              onClick={() => deactivateMutation.mutate()}
              isLoading={deactivateMutation.isPending}
              leftIcon={<UserX className="h-4 w-4" />}
            >
              Deactivate
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={() => activateMutation.mutate()}
              isLoading={activateMutation.isPending}
              leftIcon={<UserCheck className="h-4 w-4" />}
            >
              Activate
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>User Details</CardTitle>
          </CardHeader>
          <dl className="space-y-4">
            <div className="flex justify-between">
              <dt className="text-sm text-surface-500">User ID</dt>
              <dd className="text-sm font-mono text-surface-900 dark:text-surface-100">{user.id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-surface-500">Username</dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">{user.username}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-surface-500">Email</dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">{user.email}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-surface-500">Status</dt>
              <dd><StatusBadge status={user.is_active ? "active" : "inactive"} /></dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-surface-500">Superuser</dt>
              <dd>{user.is_superuser ? <Badge variant="info">Yes</Badge> : <Badge>No</Badge>}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-surface-500">Last Login</dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">
                {user.last_login_at ? formatDateTime(user.last_login_at) : "Never"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-surface-500">Created</dt>
              <dd className="text-sm text-surface-900 dark:text-surface-100">
                {user.created_at ? formatDateTime(user.created_at) : "-"}
              </dd>
            </div>
          </dl>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Roles</CardTitle>
            <Button size="sm" onClick={() => setShowRoleModal(true)} leftIcon={<Shield className="h-4 w-4" />}>
              Assign Role
            </Button>
          </CardHeader>
          <div className="space-y-2">
            <p className="text-sm text-surface-500">No roles assigned yet.</p>
          </div>
        </Card>
      </div>

      <Modal
        isOpen={showRoleModal}
        onClose={() => setShowRoleModal(false)}
        title="Assign Role"
      >
        <div className="space-y-4">
          <Select
            label="Select Role"
            placeholder="Choose a role..."
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            options={(roles || []).map((r) => ({ value: r.id, label: r.name }))}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowRoleModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => selectedRole && assignRoleMutation.mutate(selectedRole)}
              disabled={!selectedRole}
              isLoading={assignRoleMutation.isPending}
            >
              Assign
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
