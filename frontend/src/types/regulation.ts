export type RegulationCategory =
  | "data_protection"
  | "financial"
  | "environmental"
  | "health_safety"
  | "corporate_governance"
  | "trade_compliance"
  | "employment"
  | "anti_money_laundering"
  | "cybersecurity"
  | "other";

export type RegulationJurisdiction =
  | "international"
  | "national"
  | "state"
  | "regional"
  | "local";

export type RegulationStatus =
  | "draft"
  | "active"
  | "pending_repeal"
  | "repealed"
  | "superseded";

export interface RegulationRequirement {
  code: string;
  title: string;
  description: string;
  is_mandatory: boolean;
  risk_weight: number;
}

export interface Regulation {
  id: string;
  title: string;
  code: string;
  description: string;
  category: RegulationCategory;
  jurisdiction: RegulationJurisdiction;
  issuing_body: string;
  effective_date: string;
  status: RegulationStatus;
  version: number;
  tags: string[];
  parent_regulation_id: string | null;
  superseded_by_id: string | null;
  requirements: RegulationRequirement[];
  created_at: string;
  updated_at: string;
}

export interface RegulationCreateRequest {
  title: string;
  code: string;
  description: string;
  category: RegulationCategory;
  jurisdiction: RegulationJurisdiction;
  issuing_body: string;
  effective_date: string;
  tags?: string[];
  parent_regulation_id?: string;
}

export interface RegulationFilters {
  status?: RegulationStatus;
  category?: RegulationCategory;
  jurisdiction?: RegulationJurisdiction;
  search?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}
