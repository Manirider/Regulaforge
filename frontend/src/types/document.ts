export type ArtifactType =
  | "regulation"
  | "policy"
  | "procedure"
  | "report"
  | "assessment"
  | "evidence"
  | "certification"
  | "correspondence"
  | "other";

export type ProcessingStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed";

export interface Document {
  id: string;
  title: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  artifact_type: ArtifactType;
  tenant_id: string;
  processing_status: ProcessingStatus;
  is_verified: boolean;
  description: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
