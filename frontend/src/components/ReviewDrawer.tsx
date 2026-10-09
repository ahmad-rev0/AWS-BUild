import { FormEvent, useState } from "react";
import { RECOMMENDATION_LABEL, eventLine, formatMoney, formatWhen } from "../lib/format";
import type { Approval, Assignment, AuditEvent, ClashReport, DistrictNeedRecord, Proposal, Role, SseEvent } from "../types/api";
import type { DrawerTab } from "../hooks/useReviewWorkflow";

interface ReviewDrawerProps {
  open: boolean;
  tab: DrawerTab;
  role: Role;
  proposal: Proposal | null;
  report: ClashReport | null;
  events: SseEvent[];
  audit: AuditEvent[];
  auditError: string;
  approval: Approval | null;
  assignment: Assignment | null;
  deciding: boolean;
  gaps: DistrictNeedRecord[];
  onTab: (tab: DrawerTab) => void;
  onClose: () => void;
  onCommit: (districtId: string) => void;
  onReject: (actor: string, reason: string) => void;
  onShowOnMap: (districtId: string) => void;
}

export function ReviewDrawer({
  open,
  tab,
  role,
  proposal,
  report,
  events,
  audit,
  auditError,
  approval,
  assignment,
  deciding,
  gaps,
  onTab,
  onClose,
  onCommit,
  onReject,
  onShowOnMap,
}: ReviewDrawerProps) {
  const [actor, setActor] = useState("demo-approver");
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  if (!open) return null;
  const redirect = report?.memo.redirect_district_id;
  const redirectName = gaps.find((item) => item.district_id === redirect)?.district_name ?? redirect;
  const canCommit = role === "approver" && (proposal?.status === "REVIEWED" || proposal?.status === "APPROVED");
  const canReject = role === "approver" && proposal?.status === "REVIEWED" && Boolean(report) && !approval;
  const budget = proposal ? formatMoney(proposal.budget_usd) : "";
  const assignedName = gaps.find((item) => item.district_id === assignment?.district_id)?.district_name;

  function reject(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) {
      setReasonError("A rejection reason is required.");
      return;
    }
    setReasonError("");
    onReject(actor, reason.trim());
  }

  return (
    <aside className="drawer" role="dialog" aria-label="Coordination memo">
      <header>
        <img src="/brand/memo.svg" alt="" />
        <div>
          <p className="eyebrow">Coordination memo</p>
          <h2>{report ? RECOMMENDATION_LABEL[report.memo.recommendation] : "Memo not ready"}</h2>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close memo">Close</button>
      </header>
      <div className="tabs" role="tablist">
        {(["memo", "trace", "audit"] as DrawerTab[]).map((item) => (
          <button key={item} type="button" role="tab" aria-selected={tab === item} className={tab === item ? "on" : ""} onClick={() => onTab(item)}>
            {item === "memo" ? "Memo" : item === "trace" ? "How it decided" : "Audit"}
          </button>
        ))}
      </div>
      {tab === "memo" && (
        <div className="drawer-body">
          {report ? (
            <>
              <p>{report.memo.summary}</p>
              <p className="meta-line">
                {report.source === "seeded" ? "Seeded review" : "Live review"} · model {report.model_id} · {report.latency_ms} ms
              </p>
              {report && (
                <div className="gap-callout">
                  <strong>{assignment ? `Committed to ${assignedName ?? assignment.district_id}` : "Commit the proposal budget"}</strong>
                  <p>
                    {redirect ? `The memo suggests ${redirectName}. ` : ""}
                    {assignment
                      ? `${formatMoney(assignment.amount_usd)} is recorded on that district. Choose another district to move the same budget.`
                      : `Place ${budget || "the proposal budget"} on the district you choose.`}
                  </p>
                  {gaps.map((district) => {
                    const here = assignment?.district_id === district.district_id;
                    return (
                      <button
                        key={district.district_id}
                        type="button"
                        className="primary"
                        disabled={!canCommit || deciding || here}
                        onClick={() => onCommit(district.district_id)}
                      >
                        {here ? `Committed to ${district.district_name}` : `${assignment ? "Move" : "Commit"} ${budget} to ${district.district_name}`}
                      </button>
                    );
                  })}
                  {role === "planner" && <p className="hint">Switch to Approver to commit this budget.</p>}
                  {redirect && (
                    <button type="button" className="secondary" onClick={() => onShowOnMap(redirect)}>Show suggested district</button>
                  )}
                </div>
              )}
            </>
          ) : (
            <p>Complete a review to read the coordination memo.</p>
          )}
          {approval && (
            <div className="decision">
              <strong>Decision recorded: {approval.decision}</strong>
              <p>{approval.actor} · {formatWhen(approval.decided_at)}</p>
              {approval.reason && <p>{approval.reason}</p>}
            </div>
          )}
          {canReject && (
            <form className="decision-form" onSubmit={reject}>
              <label>
                Approver
                <input value={actor} onChange={(event) => setActor(event.target.value)} />
              </label>
              <label>
                Rejection reason
                <textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Required only when rejecting" />
              </label>
              {reasonError && <p className="error">{reasonError}</p>}
              <button type="submit" className="danger" disabled={deciding}>Reject</button>
            </form>
          )}
          {role === "planner" && proposal && !assignment && (
            <p className="hint">Switch to Approver, then commit the proposal budget to a district.</p>
          )}
        </div>
      )}
      {tab === "trace" && (
        <ol className="trace">
          {events.length === 0 && <li>Tool calls appear here while the review runs.</li>}
          {events.map((event, index) => (
            <li key={`${event.type}-${index}`}>
              <span>{event.type.replace("_", " ")}</span>
              <p>{eventLine(event)}</p>
            </li>
          ))}
        </ol>
      )}
      {tab === "audit" && (
        <ol className="trace">
          {auditError && <li className="error">{auditError}</li>}
          {audit.length === 0 && !auditError && <li>No audit rows for this review yet.</li>}
          {audit.map((event) => (
            <li key={event.event_id}>
              <span>{event.event_type.replace(/_/g, " ")} · {formatWhen(event.timestamp)}</span>
              <p>{event.payload_summary}</p>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
