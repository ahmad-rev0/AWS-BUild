export type Role = "planner" | "approver";
export type ProposalStatus = "SUBMITTED" | "REVIEWED" | "APPROVED" | "REJECTED";
export type VerdictLabel = "DUPLICATE" | "OVERLAPPING" | "COMPLEMENTARY" | "UNRELATED";
export type Recommendation = "MERGE" | "CO_FINANCE" | "PROCEED" | "REDIRECT";
export type Source = "seeded" | "user" | "worldbank_api" | "iati" | "live";

export interface ProposalCreate {
  title: string;
  description: string;
  city_id: string;
  district_id?: string;
  sector: string;
  budget_usd: string;
  start_date?: string;
  end_date?: string;
  scenario_key?: string;
  source: "seeded" | "user";
  source_url?: string;
}

export interface Proposal extends ProposalCreate {
  proposal_id: string;
  status: ProposalStatus;
  submitted_at: string;
}

export interface Verdict {
  project_id: string;
  label: VerdictLabel;
  confidence: number;
  matching_attributes: string[];
  reasoning: string;
}

export interface Memo {
  recommendation: Recommendation;
  summary: string;
  redirect_district_id?: string;
}

export interface ClashReport {
  proposal_id: string;
  candidates: Verdict[];
  memo: Memo;
  model_id: string;
  latency_ms: number;
  source: "seeded" | "live";
}

export interface ReviewCreated {
  review_id: string;
}

export interface ApprovalCreate {
  review_id: string;
  decision: "APPROVED" | "REJECTED";
  actor: string;
  role: Role;
  reason?: string;
}

export interface Approval {
  approval_id: string;
  review_id: string;
  proposal_id: string;
  actor: string;
  role: Role;
  decision: "APPROVED" | "REJECTED";
  decided_at: string;
  reason?: string;
}

export interface AssignmentCreate {
  district_id: string;
  actor: string;
  role: Role;
}

export interface Assignment {
  assignment_id: string;
  proposal_id: string;
  district_id: string;
  amount_usd: string;
  actor: string;
  role: Role;
  assigned_at: string;
}

export interface SseEvent {
  type: "status" | "tool_call" | "verdict" | "done" | "error";
  name?: string | null;
  ms?: number | null;
  payload?: Record<string, unknown> | null;
}

export interface DistrictNeedRecord {
  district_id: string;
  district_name: string;
  need_score: number;
  funded_commitments_usd: number;
  commitments_per_capita: number;
  funding_gap: boolean;
  indicator_quality: "measured" | "estimated" | "illustrative";
  snapshot_date: string;
  source: string;
  source_url: string;
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  proposal_id?: string;
  review_id?: string;
  project_id?: string;
  approval_id?: string;
  actor?: string;
  role?: Role;
  payload_summary: string;
}

export interface ReviewReportResponse {
  review_id: string;
  proposal: Proposal;
  report: ClashReport;
}

export interface ProposalWorkspace {
  proposal: Proposal;
  review_id: string | null;
  report: ClashReport | null;
  approval: Approval | null;
  assignment: Assignment | null;
}

export type ReviewReport = ReviewReportResponse;
