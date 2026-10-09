import { formatMoney } from "../lib/format";
import type { Assignment, DistrictNeedRecord, Proposal, Role } from "../types/api";
import type { ReviewStage } from "../hooks/useReviewWorkflow";

interface DemoGuideProps {
  stage: ReviewStage;
  role: Role;
  hasReport: boolean;
  assignment: Assignment | null;
  proposal: Proposal | null;
  gaps: DistrictNeedRecord[];
  busy: boolean;
  deciding: boolean;
  onCompare: () => void;
  onBecomeApprover: () => void;
  onCommit: (districtId: string) => void;
  onReset: () => void;
}

export function DemoGuide({
  stage,
  role,
  hasReport,
  assignment,
  proposal,
  gaps,
  busy,
  deciding,
  onCompare,
  onBecomeApprover,
  onCommit,
  onReset,
}: DemoGuideProps) {
  const finished = Boolean(assignment);
  const readyToCommit = hasReport && (proposal?.status === "REVIEWED" || proposal?.status === "APPROVED");
  const step = !hasReport ? 1 : role !== "approver" && !finished ? 2 : !finished ? 3 : 4;
  const budget = proposal ? formatMoney(proposal.budget_usd) : "the proposal budget";
  const assignedName = gaps.find((item) => item.district_id === assignment?.district_id)?.district_name;
  const title = finished
    ? `${formatMoney(assignment?.amount_usd ?? 0)} is on ${assignedName ?? "the chosen district"}.`
    : readyToCommit && role === "approver"
      ? "Choose the district that receives this budget."
      : hasReport
        ? "The comparison is ready."
        : busy
          ? "Comparing the proposal now."
          : "Compare the proposal, then place its budget.";
  const body = finished
    ? `The approver committed this proposal's budget to ${assignedName ?? "the selected district"}. Use the other district button to move the same budget. This does not change World Bank project records.`
    : readyToCommit && role === "approver"
      ? `${budget} stays with this proposal until you commit it. Each district button places that full amount on that district.`
      : hasReport
        ? "Switch to Approver. That role can commit the proposal budget onto either district."
        : "Start with the comparison. After it finishes, an approver commits the proposal budget to one of the two districts on the map.";

  return (
    <section className="guide" aria-live="polite">
      <p className="eyebrow">Demo walkthrough · step {step} of 4</p>
      <h2>{title}</h2>
      <p>{body}</p>
      <div className="guide-actions">
        {!hasReport && (
          <button type="button" className="primary" disabled={busy} onClick={onCompare}>
            {busy ? "Comparing…" : "1. Compare this proposal"}
          </button>
        )}
        {hasReport && !finished && role === "planner" && (
          <button type="button" className="primary" onClick={onBecomeApprover}>2. Switch to Approver</button>
        )}
        {readyToCommit && role === "approver" && gaps.map((district) => {
          const here = assignment?.district_id === district.district_id;
          return (
            <button
              key={district.district_id}
              type="button"
              className="primary"
              disabled={busy || deciding || here || stage === "submitting"}
              onClick={() => onCommit(district.district_id)}
            >
              {here ? `Committed to ${district.district_name}` : `${assignment ? "Move" : "Commit"} ${budget} to ${district.district_name}`}
            </button>
          );
        })}
        <button type="button" className="secondary" disabled={busy || deciding} onClick={onReset}>
          Start over
        </button>
      </div>
    </section>
  );
}
