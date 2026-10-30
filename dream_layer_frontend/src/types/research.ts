export type ResultStatus = 'success' | 'not_applicable' | 'insufficient_data' | 'unavailable_dependency' | 'failed_evaluation' | 'abstention' | 'invalid_legacy_result';
export interface ResearchRecord {
  id: string; kind: string; experiment_id: string; created_at: string;
  [key: string]: unknown;
}
export interface Experiment extends ResearchRecord { config: Record<string, unknown>; config_hash: string }
export interface MetricResult extends ResearchRecord {
  metric_id: string; metric_version: string; scope: string; score: number | null;
  status: ResultStatus; reason: string | null; special_value?: string; supersedes?: string; supersedes_ids?: string[]; evaluation_attempt?: number;
}
export interface Asset extends ResearchRecord {
  trial_id: string; original_filename: string; sha256: string; locator: string;
  media: { modality: 'image' | 'video'; duration: number | null; width: number; height: number };
}
export interface ResearchDetail { experiment: Experiment; records: ResearchRecord[]; job: { state: string; error: string | null } }
export interface Rubric { version: string; criteria: { id: string; description: string }[] }
export interface BlindAssignment {
  id: string; rater_id: string; mode: 'pointwise' | 'pairwise'; rubric: Rubric;
  prompt_text: string; completed: boolean; practice: boolean;
  media: { slot: number; modality: 'image' | 'video'; url: string }[];
  references: { slot: number; modality: 'image' | 'video'; url: string }[];
}
