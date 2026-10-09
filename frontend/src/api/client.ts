import type {
  CatalogCommitRequest,
  CatalogCommitment,
  CatalogCompareRequest,
  CatalogCompareResponse,
  CatalogRecommendation,
  CatalogProject,
  CatalogSummary,
} from "../types/catalog";
import type {
  Approval,
  ApprovalCreate,
  Assignment,
  AssignmentCreate,
  AuditEvent,
  ClashReport,
  DistrictNeedRecord,
  Proposal,
  ProposalCreate,
  ProposalWorkspace,
  ReviewCreated,
  ReviewReportResponse,
  SseEvent,
} from "../types/api";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const eventTypes = new Set(["status", "tool_call", "verdict", "done", "error"]);

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = body?.detail;
  if (typeof detail === "string" && detail.trim()) return new ApiError(response.status, detail);
  if (Array.isArray(detail)) {
    const text = detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") return item.msg;
        return "Request could not be validated.";
      })
      .join(" ");
    return new ApiError(response.status, text);
  }
  return new ApiError(response.status, response.statusText || "Request failed");
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as T;
}

export function parseSseBlock(block: string): SseEvent | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim())
    .join("\n");
  if (!data) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    throw new Error("A review event was not valid JSON.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("A review event could not be validated.");
  }
  const event = parsed as Record<string, unknown>;
  if (typeof event.type !== "string" || !eventTypes.has(event.type)) {
    throw new Error("A review event could not be validated.");
  }
  if (event.name != null && typeof event.name !== "string") throw new Error("A review event could not be validated.");
  if (event.ms != null && (typeof event.ms !== "number" || !Number.isFinite(event.ms) || event.ms < 0)) {
    throw new Error("A review event could not be validated.");
  }
  if (event.payload != null && (typeof event.payload !== "object" || Array.isArray(event.payload))) {
    throw new Error("A review event could not be validated.");
  }
  return {
    type: event.type as SseEvent["type"],
    name: typeof event.name === "string" ? event.name : null,
    ms: typeof event.ms === "number" ? event.ms : null,
    payload: (event.payload as Record<string, unknown> | null) ?? null,
  };
}

export async function streamReview(
  reviewId: string,
  onEvent: (event: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${apiBase}/reviews/${reviewId}/events`, { signal });
  if (!response.ok) throw await errorFrom(response);
  const reader = response.body?.getReader();
  if (!reader) {
    for (const block of (await response.text()).split(/\n\n/)) {
      const event = parseSseBlock(block);
      if (event) onEvent(event);
    }
    return;
  }
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const parts = buffer.split(/\n\n/);
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const event = parseSseBlock(part);
      if (event) onEvent(event);
    }
    if (done) break;
  }
  if (buffer.trim()) {
    const event = parseSseBlock(buffer);
    if (event) onEvent(event);
  }
}

export const api = {
  createProposal: (payload: ProposalCreate) => request<Proposal>("/proposals", "POST", payload),
  createReview: (proposalId: string) => request<ReviewCreated>(`/proposals/${proposalId}/review`, "POST"),
  getReview: (reviewId: string) => request<ReviewReportResponse>(`/reviews/${reviewId}`),
  getProposal: (proposalId: string) => request<ProposalWorkspace>(`/proposals/${proposalId}`),
  createApproval: (payload: ApprovalCreate) => request<Approval>("/approvals", "POST", payload),
  assignBudget: (proposalId: string, payload: AssignmentCreate) =>
    request<Assignment>(`/proposals/${proposalId}/assignment`, "POST", payload),
  getAudit: (reviewId: string) => request<AuditEvent[]>(`/audit?review_id=${encodeURIComponent(reviewId)}`),
  getGaps: () => request<DistrictNeedRecord[]>("/gaps"),
  getCatalog: () => request<CatalogSummary>("/catalog"),
  getCatalogProjects: (country: string, city: string) =>
    request<CatalogProject[]>(
      `/catalog/projects?country=${encodeURIComponent(country)}&city=${encodeURIComponent(city)}&limit=8`,
    ),
  compareCatalog: (payload: CatalogCompareRequest) => request<CatalogCompareResponse>("/catalog/compare", "POST", payload),
  recommendCatalog: (payload: CatalogCompareRequest) => request<CatalogRecommendation>("/catalog/recommend", "POST", payload),
  commitCatalog: (payload: CatalogCommitRequest) => request<CatalogCommitment>("/catalog/commit", "POST", payload),
  getCatalogCommitment: () => request<CatalogCommitment>("/catalog/commitment"),
  resetDemo: async () => {
    const response = await fetch(`${apiBase}/demo/reset`, { method: "POST" });
    if (!response.ok) throw await errorFrom(response);
  },
  getReport: (reviewId: string) => request<{ report: ClashReport }>(`/reviews/${reviewId}`),
};
