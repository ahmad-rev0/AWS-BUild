import { useEffect, useState } from "react";
import "leaflet/dist/leaflet.css";
import { CatalogWorkspace } from "../components/CatalogWorkspace";
import { DemoGuide } from "../components/DemoGuide";
import { MapWorkspace } from "../components/MapWorkspace";
import { ProposalForm } from "../components/ProposalForm";
import { ReviewDrawer } from "../components/ReviewDrawer";
import { VerdictList } from "../components/VerdictList";
import { useReviewWorkflow } from "../hooks/useReviewWorkflow";
import { RECOMMENDATION_LABEL } from "../lib/format";
import { CANONICAL_PROPOSAL } from "../lib/scenario";
import type { ProposalCreate, Role } from "../types/api";

const steps = ["Intake", "Review", "Verdicts", "Memo", "Commit"] as const;

export function PlannerDashboard() {
  const workflow = useReviewWorkflow();
  const [mode, setMode] = useState<"catalog" | "demo">("catalog");
  const [draft, setDraft] = useState<ProposalCreate>(CANONICAL_PROPOSAL);
  const busy = workflow.stage === "submitting" || workflow.stage === "streaming";
  const stepIndex = workflow.assignment ? 4 : workflow.report ? 3 : workflow.verdicts.length ? 2 : busy ? 1 : 0;

  const { setDrawerOpen, setDrawerTab } = workflow;
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.key === "Escape") setDrawerOpen(false);
      if (event.key.toLowerCase() === "m") {
        setDrawerTab("memo");
        setDrawerOpen((open) => !open);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setDrawerOpen, setDrawerTab]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img className="brand-seal" src="/brand/seal.svg" alt="" />
          <div>
            <strong>Atlas11</strong>
            <span>SDG 11 coordination control room</span>
          </div>
        </div>
        <div className="role" role="tablist" aria-label="Workspace">
          <button type="button" className={mode === "catalog" ? "on" : ""} onClick={() => setMode("catalog")}>World Bank</button>
          <button type="button" className={mode === "demo" ? "on" : ""} onClick={() => setMode("demo")}>Scripted demo</button>
        </div>
        <p className="snapshot">
          {mode === "catalog"
            ? "World Bank Projects API · Pakistan and Bangladesh"
            : `Data snapshot: ${workflow.gaps[0]?.snapshot_date ?? "TBD: needs source"}`}
        </p>
        {mode === "demo" && <div className="role" role="radiogroup" aria-label="Role">
          {(["planner", "approver"] as Role[]).map((item) => (
            <button
              key={item}
              type="button"
              role="radio"
              aria-checked={workflow.role === item}
              className={workflow.role === item ? "on" : ""}
              onClick={() => workflow.setRole(item)}
            >
              {item === "planner" ? "Planner" : "Approver"}
            </button>
          ))}
        </div>}
        {mode === "demo" && <button
          type="button"
          className="memo-button"
          aria-expanded={workflow.drawerOpen}
          onClick={() => {
            workflow.setDrawerTab("memo");
            workflow.setDrawerOpen(true);
          }}
        >
          Review memo
          {workflow.report && <i />}
        </button>}
      </header>
      {mode === "catalog" ? <CatalogWorkspace /> : <>
      <ol className="progress">
        {steps.map((label, index) => (
          <li key={label} className={index < stepIndex ? "done" : index === stepIndex ? "current" : ""}>
            <span>{index + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      {workflow.error && <p className="banner" role="alert">{workflow.error}</p>}
      <div className="workspace">
        <aside className="intake">
          <DemoGuide
            stage={workflow.stage}
            role={workflow.role}
            hasReport={Boolean(workflow.report)}
            assignment={workflow.assignment}
            proposal={workflow.proposal}
            gaps={workflow.gaps}
            busy={busy}
            deciding={workflow.deciding}
            onCompare={() => void workflow.submit(draft)}
            onBecomeApprover={() => {
              workflow.setRole("approver");
              workflow.setDrawerTab("memo");
              workflow.setDrawerOpen(true);
            }}
            onCommit={(districtId) => void workflow.commitToDistrict(districtId)}
            onReset={() => void workflow.resetDemo()}
          />
          <details className="proposal-details">
            <summary>Proposal details · seeded US$24M transit corridor</summary>
            <ProposalForm
              draft={draft}
              disabled={busy}
              recordedReady={workflow.recordedReady}
              gaps={workflow.gaps}
              onChange={setDraft}
              onSubmit={() => void workflow.submit(draft)}
              onReset={() => setDraft(CANONICAL_PROPOSAL)}
              onOpenRecorded={() => void workflow.openRecorded()}
            />
          </details>
          {workflow.report && (
            <button
              type="button"
              className="memo-teaser"
              onClick={() => {
                workflow.setDrawerTab("memo");
                workflow.setDrawerOpen(true);
              }}
            >
              <span>Recommendation</span>
              <strong>{RECOMMENDATION_LABEL[workflow.report.memo.recommendation]}</strong>
              <small>Open the memo, trace, and sign-off. Shortcut M.</small>
            </button>
          )}
          <VerdictList
            verdicts={workflow.verdicts}
            selectedId={workflow.selectedProjectId}
            loading={busy}
            statusLine={workflow.statusLine}
            onSelect={workflow.selectProject}
          />
        </aside>
        <MapWorkspace
          gaps={workflow.gaps}
          gapsError={workflow.gapsError}
          proposal={workflow.proposal}
          role={workflow.role}
          assignment={workflow.assignment}
          deciding={workflow.deciding}
          verdicts={workflow.verdicts}
          selectedProjectId={workflow.selectedProjectId}
          focusedDistrictId={workflow.focusedDistrictId}
          onFocus={workflow.setFocusedDistrictId}
          onCommit={(districtId) => void workflow.commitToDistrict(districtId)}
        />
        <ReviewDrawer
          open={workflow.drawerOpen}
          tab={workflow.drawerTab}
          role={workflow.role}
          proposal={workflow.proposal}
          report={workflow.report}
          events={workflow.events}
          audit={workflow.audit}
          auditError={workflow.auditError}
          approval={workflow.approval}
          assignment={workflow.assignment}
          deciding={workflow.deciding}
          gaps={workflow.gaps}
          onTab={(tab) => {
            workflow.setDrawerTab(tab);
            if (tab === "audit") void workflow.loadAudit();
          }}
          onClose={() => workflow.setDrawerOpen(false)}
          onCommit={(districtId) => void workflow.commitToDistrict(districtId)}
          onReject={(actor, reason) => void workflow.reject(actor, reason)}
          onShowOnMap={(districtId) => {
            workflow.setFocusedDistrictId(districtId);
            workflow.setDrawerOpen(false);
          }}
        />
      </div>
      </>}
    </div>
  );
}
