export type EntityType =
  | "organization"
  | "department"
  | "subsidiary"
  | "project"
  | "system"
  | "third_party"
  | "other";

export interface Entity {
  id: string;
  name: string;
  entity_type: EntityType;
  tenant_id: string;
  description: string | null;
  parent_entity_id: string | null;
  is_active: boolean;
  tags: string[];
  attributes: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EntityCreateRequest {
  name: string;
  entity_type: EntityType;
  tenant_id: string;
  description?: string;
  parent_entity_id?: string;
  tags?: string[];
  attributes?: Record<string, unknown>;
}
