export type AssessmentStatus =
  | "scheduled"
  | "in_progress"
  | "completed"
  | "approved"
  | "cancelled"
  | "rejected";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface AssessmentFinding {
  id: string;
  requirement_code: string;
  title: string;
  description: string;
  risk_level: RiskLevel;
  impact_score: number | null;
  likelihood_score: number | null;
  remediation_recommendation: string | null;
  assigned_to: string | null;
  created_at: string;
}

export interface Assessment {
  id: string;
  title: string;
  entity_id: string;
  entity_name?: string;
  regulation_ids: string[];
  assessor_id: string;
  due_date: string;
  status: AssessmentStatus;
  findings: AssessmentFinding[];
  score: number | null;
  scope_description: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AssessmentCreateRequest {
  title: string;
  entity_id: string;
  regulation_ids: string[];
  assessor_id: string;
  due_date: string;
  scope_description?: string;
}

export interface FindingCreateRequest {
  requirement_code: string;
  title: string;
  description: string;
  risk_level: RiskLevel;
  impact_score?: number;
  likelihood_score?: number;
  remediation_recommendation?: string;
  assigned_to?: string;
}
