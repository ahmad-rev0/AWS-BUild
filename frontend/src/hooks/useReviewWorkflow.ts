import { useEffect, useRef, useState } from "react";
import { ApiError, api, streamReview } from "../api/client";
import { districtFromAttributes } from "../lib/geo";
import { eventLine, isVerdict } from "../lib/format";
import { DEMO_PROPOSAL_ID, isCanonical } from "../lib/scenario";
import type {
  Approval,
  Assignment,
  AuditEvent,
  ClashReport,
  DistrictNeedRecord,
  Proposal,
  ProposalCreate,
  Role,
  SseEvent,
  Verdict,
} from "../types/api";

export type ReviewStage = "idle" | "submitting" | "streaming" | "complete" | "error";
export type DrawerTab = "memo" | "trace" | "audit";

function text(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") return "";
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Unexpected error";
}

function verdictFrom(payload: Record<string, unknown> | null | undefined): Verdict | null {
  if (!payload || !isVerdict(payload)) return null;
  const attributes = payload.matching_attributes;
  if (!Array.isArray(attributes) || attributes.some((item) => typeof item !== "string")) return null;
  return {
    project_id: String(payload.project_id),
    label: payload.label as Verdict["label"],
    confidence: Number(payload.confidence),
    matching_attributes: attributes,
    reasoning: String(payload.reasoning),
  };
}

export function useReviewWorkflow() {
  const [role, setRole] = useState<Role>("planner");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [report, setReport] = useState<ClashReport | null>(null);
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [streamVerdicts, setStreamVerdicts] = useState<Verdict[]>([]);
  const [stage, setStage] = useState<ReviewStage>("idle");
  const [statusLine, setStatusLine] = useState("Ready for the seeded coordination review.");
  const [error, setError] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("memo");
  const [focusedDistrictId, setFocusedDistrictId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [approval, setApproval] = useState<Approval | null>(null);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [auditError, setAuditError] = useState("");
  const [recordedReady, setRecordedReady] = useState(false);
  const [gaps, setGaps] = useState<DistrictNeedRecord[]>([]);
  const [gapsError, setGapsError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const terminalRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    api.getGaps()
      .then((rows) => {
        if (!controller.signal.aborted) setGaps(rows);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setGapsError(text(reason) || "District gap records are unavailable.");
      });
    api.getProposal(DEMO_PROPOSAL_ID)
      .then((workspace) => {
        if (controller.signal.aborted || !workspace.report || !workspace.review_id) return;
        setProposal(workspace.proposal);
        setReviewId(workspace.review_id);
        setReport(workspace.report);
        setApproval(workspace.approval);
        setAssignment(workspace.assignment);
        if (workspace.assignment) setFocusedDistrictId(workspace.assignment.district_id);
        setRecordedReady(true);
        setStage("complete");
        setStatusLine(
          workspace.assignment
            ? "This proposal's budget is already committed. Choose another district to move it."
            : "The comparison is ready. An approver can commit the budget to a district.",
        );
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiError && reason.status === 404) return;
        if (!controller.signal.aborted) setError(text(reason));
      });
    return () => controller.abort();
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  async function play(nextProposal: Proposal, nextReviewId: string, existingApproval: Approval | null) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    terminalRef.current = false;
    setProposal(nextProposal);
    setReviewId(nextReviewId);
    setReport(null);
    setEvents([]);
    setStreamVerdicts([]);
    setApproval(existingApproval);
    setSelectedProjectId(null);
    setError("");
    setStage("streaming");
    setStatusLine("Comparing the proposal with existing work…");
    try {
      await streamReview(
        nextReviewId,
        (event) => {
          if (terminalRef.current) return;
          setEvents((current) => [...current, event]);
          setStatusLine(eventLine(event));
          if (event.type === "verdict") {
            const verdict = verdictFrom(event.payload);
            if (!verdict) {
              terminalRef.current = true;
              throw new Error("A verdict event could not be validated.");
            }
            setStreamVerdicts((current) => [...current, verdict]);
          }
          if (event.type === "error") {
            terminalRef.current = true;
            const detail = typeof event.payload?.message === "string" ? event.payload.message : "The review stream reported an error.";
            throw new Error(detail);
          }
          if (event.type === "done") terminalRef.current = true;
        },
        controller.signal,
      );
      if (!terminalRef.current) throw new Error("The review stream ended before a validated report.");
      const finalReport = await api.getReview(nextReviewId);
      if (controller.signal.aborted) return;
      setProposal(finalReport.proposal);
      setReport(finalReport.report);
      setReviewId(finalReport.review_id);
      setRecordedReady(true);
      setStage("complete");
      setStatusLine("Comparison ready. Read the two results, then open the memo.");
    } catch (reason: unknown) {
      if (controller.signal.aborted || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setStage("error");
      setError(text(reason) || "The review could not be completed.");
    }
  }

  async function openRecorded() {
    setStage("submitting");
    setError("");
    setStatusLine("Opening the recorded coordination review…");
    try {
      const workspace = await api.getProposal(DEMO_PROPOSAL_ID);
      if (workspace.review_id && (workspace.report || workspace.proposal.status === "SUBMITTED")) {
        await play(workspace.proposal, workspace.review_id, workspace.approval);
        return;
      }
      if (workspace.proposal.status === "SUBMITTED") {
        const created = await api.createReview(workspace.proposal.proposal_id);
        await play(workspace.proposal, created.review_id, null);
        return;
      }
      throw new Error("The recorded proposal has no review to open.");
    } catch (reason: unknown) {
      setStage("error");
      setError(text(reason) || "The recorded review could not be opened.");
    }
  }

  async function submit(draft: ProposalCreate) {
    setStage("submitting");
    setError("");
    setReport(null);
    setApproval(null);
    setAssignment(null);
    setEvents([]);
    setStreamVerdicts([]);
    setStatusLine("Submitting the seeded transit proposal…");
    try {
      const created = await api.createProposal(draft);
      setProposal(created);
      setStatusLine("Creating the coordination review…");
      const review = await api.createReview(created.proposal_id);
      await play(created, review.review_id, null);
    } catch (reason: unknown) {
      if (reason instanceof ApiError && reason.status === 409 && isCanonical(draft)) {
        await openRecorded();
        return;
      }
      setStage("error");
      setError(text(reason) || "The proposal could not be submitted.");
    }
  }

  async function decide(decision: "APPROVED" | "REJECTED", actor: string, reason?: string) {
    if (!reviewId) return;
    setDeciding(true);
    setError("");
    try {
      const recorded = await api.createApproval({
        review_id: reviewId,
        decision,
        actor: actor.trim() || "demo-approver",
        role: "approver",
        reason,
      });
      setApproval(recorded);
      setProposal((current) => (current ? { ...current, status: recorded.decision } : current));
      setDrawerTab("memo");
    } catch (reason: unknown) {
      setError(text(reason) || "The coordination decision could not be recorded.");
    } finally {
      setDeciding(false);
    }
  }

  async function commitToDistrict(districtId: string) {
    if (!proposal) return;
    setDeciding(true);
    setError("");
    try {
      const recorded = await api.assignBudget(proposal.proposal_id, {
        district_id: districtId,
        actor: "demo-approver",
        role: "approver",
      });
      setAssignment(recorded);
      setFocusedDistrictId(districtId);
      setDrawerOpen(false);
      setStatusLine("Proposal budget committed to the selected district.");
    } catch (reason: unknown) {
      setError(text(reason) || "The budget could not be committed to that district.");
    } finally {
      setDeciding(false);
    }
  }

  async function loadAudit() {
    if (!reviewId) return;
    setAuditError("");
    try {
      setAudit(await api.getAudit(reviewId));
    } catch (reason: unknown) {
      setAuditError(text(reason) || "The audit trail could not be loaded.");
    }
  }

  async function resetDemo() {
    abortRef.current?.abort();
    setError("");
    setStatusLine("Clearing the previous walkthrough…");
    try {
      await api.resetDemo();
      setProposal(null);
      setReviewId(null);
      setReport(null);
      setEvents([]);
      setStreamVerdicts([]);
      setApproval(null);
      setAssignment(null);
      setSelectedProjectId(null);
      setFocusedDistrictId(null);
      setDrawerOpen(false);
      setDrawerTab("memo");
      setAudit([]);
      setRecordedReady(false);
      setRole("planner");
      setStage("idle");
      setStatusLine("Ready. Compare the seeded proposal.");
    } catch (reason: unknown) {
      setStage("error");
      setError(text(reason) || "The demo could not be reset.");
    }
  }

  function selectProject(projectId: string) {
    setSelectedProjectId(projectId);
    const verdict = (report?.candidates ?? streamVerdicts).find((item) => item.project_id === projectId);
    const districtId = verdict ? districtFromAttributes(verdict.matching_attributes) : null;
    if (districtId) setFocusedDistrictId(districtId);
  }

  const verdicts = report?.candidates ?? streamVerdicts;

  return {
    role,
    setRole,
    proposal,
    reviewId,
    report,
    events,
    verdicts,
    stage,
    statusLine,
    error,
    drawerOpen,
    setDrawerOpen,
    drawerTab,
    setDrawerTab,
    focusedDistrictId,
    setFocusedDistrictId,
    selectedProjectId,
    selectProject,
    approval,
    assignment,
    commitToDistrict,
    deciding,
    audit,
    auditError,
    recordedReady,
    gaps,
    gapsError,
    submit,
    openRecorded,
    resetDemo,
    approve: (actor: string) => decide("APPROVED", actor),
    reject: (actor: string, reason: string) => decide("REJECTED", actor, reason),
    loadAudit,
  };
}
