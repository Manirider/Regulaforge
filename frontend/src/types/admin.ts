export interface Role {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  is_system_role: boolean;
}

export interface CreateRoleRequest {
  name: string;
  description?: string | null;
  permissions?: string[];
}

export interface UpdateUserRequest {
  full_name?: string;
  is_active?: boolean;
  is_superuser?: boolean;
}

export interface UserFilters {
  email?: string;
  is_active?: boolean;
}
