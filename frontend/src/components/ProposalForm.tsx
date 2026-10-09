import { FormEvent } from "react";
import { formatMoney } from "../lib/format";
import { CANONICAL_PROPOSAL, isCanonical } from "../lib/scenario";
import type { DistrictNeedRecord, ProposalCreate } from "../types/api";

interface ProposalFormProps {
  draft: ProposalCreate;
  disabled: boolean;
  recordedReady: boolean;
  gaps: DistrictNeedRecord[];
  onChange: (draft: ProposalCreate) => void;
  onSubmit: () => void;
  onReset: () => void;
  onOpenRecorded: () => void;
}

function problems(draft: ProposalCreate): string[] {
  const notes: string[] = [];
  if (!draft.title.trim()) notes.push("Title is required.");
  if (!draft.description.trim()) notes.push("Description is required.");
  if (!draft.city_id.trim()) notes.push("City ID is required.");
  if (!draft.sector.trim()) notes.push("Sector is required.");
  if (!/^\d+(\.\d+)?$/.test(draft.budget_usd.trim())) notes.push("Budget must be a non-negative number of US dollars.");
  if (draft.start_date && draft.end_date && draft.end_date < draft.start_date) notes.push("End date must follow the start date.");
  return notes;
}

export function ProposalForm({
  draft,
  disabled,
  recordedReady,
  gaps,
  onChange,
  onSubmit,
  onReset,
  onOpenRecorded,
}: ProposalFormProps) {
  const canonical = isCanonical(draft);
  const notes = problems(draft);
  const district = gaps.find((item) => item.district_id === draft.district_id);
  const budgetPreview = /^\d+(\.\d+)?$/.test(draft.budget_usd.trim()) ? formatMoney(draft.budget_usd) : "";

  function update(patch: Partial<ProposalCreate>) {
    onChange({ ...draft, ...patch });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!disabled && canonical && notes.length === 0) onSubmit();
  }

  return (
    <form className="proposal" onSubmit={submit}>
      <div className="seeded-badge">Seeded for demo · illustrative local data</div>
      <label>
        Title
        <input value={draft.title} onChange={(event) => update({ title: event.target.value })} maxLength={300} />
      </label>
      <label>
        Description
        <textarea value={draft.description} onChange={(event) => update({ description: event.target.value })} rows={4} />
      </label>
      <div className="split">
        <label>
          Sector
          <input value={draft.sector} onChange={(event) => update({ sector: event.target.value })} />
        </label>
        <label>
          Budget (USD)
          <input inputMode="decimal" value={draft.budget_usd} onChange={(event) => update({ budget_usd: event.target.value })} />
          {budgetPreview && <small className="hint">{budgetPreview}</small>}
        </label>
      </div>
      <div className="split">
        <label>
          Start
          <input type="date" value={draft.start_date ?? ""} onChange={(event) => update({ start_date: event.target.value })} />
        </label>
        <label>
          End
          <input type="date" value={draft.end_date ?? ""} onChange={(event) => update({ end_date: event.target.value })} />
        </label>
      </div>
      {district && (
        <p className="district-preview">
          <strong>{district.district_name}</strong>
          <span>Need {district.need_score.toFixed(2)}</span>
          <span>{district.funding_gap ? "Funding gap" : "No funding gap"}</span>
          <span>{district.indicator_quality}</span>
        </p>
      )}
      <details>
        <summary>Canonical identifiers</summary>
        <label>
          City ID
          <input value={draft.city_id} onChange={(event) => update({ city_id: event.target.value })} />
        </label>
        <label>
          District ID
          <input value={draft.district_id ?? ""} onChange={(event) => update({ district_id: event.target.value })} />
        </label>
        <p className="hint">Scenario {draft.scenario_key} · source {draft.source}</p>
      </details>
      {notes.map((note) => (
        <p className="error" key={note}>{note}</p>
      ))}
      {!canonical && (
        <p className="warn">
          Cached review runs only for the canonical seeded scenario.
          <button type="button" className="text-button" onClick={onReset}>Reset scenario</button>
        </p>
      )}
      <button className="primary" type="submit" disabled={disabled || !canonical || notes.length > 0}>
        {disabled ? "Comparing…" : "Compare this proposal"}
      </button>
      {recordedReady && (
        <button className="secondary" type="button" onClick={onOpenRecorded} disabled={disabled}>
          Watch the comparison again
        </button>
      )}
      {!canonical && (
        <button className="secondary" type="button" onClick={() => onChange(CANONICAL_PROPOSAL)}>
          Restore canonical scenario
        </button>
      )}
    </form>
  );
}
