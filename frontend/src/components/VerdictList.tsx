import { useState } from "react";
import { LABEL_COLOR, LABEL_NOTE } from "../lib/format";
import { SEEDED_PROJECTS } from "../lib/scenario";
import type { Verdict, VerdictLabel } from "../types/api";

interface VerdictListProps {
  verdicts: Verdict[];
  selectedId: string | null;
  loading: boolean;
  statusLine: string;
  onSelect: (projectId: string) => void;
}

const filters: Array<VerdictLabel | "ALL"> = ["ALL", "DUPLICATE", "OVERLAPPING", "COMPLEMENTARY", "UNRELATED"];

export function VerdictList({ verdicts, selectedId, loading, statusLine, onSelect }: VerdictListProps) {
  const [filter, setFilter] = useState<VerdictLabel | "ALL">("ALL");
  const [openId, setOpenId] = useState<string | null>(null);
  const visible = filter === "ALL" ? verdicts : verdicts.filter((verdict) => verdict.label === filter);

  return (
    <section className="verdicts" aria-live="polite">
      <div className="section-head">
        <h2>Verdicts</h2>
        <span>{verdicts.length ? `${verdicts.length} candidates` : "Waiting"}</span>
      </div>
      <p className="status-line">{statusLine}</p>
      {verdicts.length > 0 && (
        <div className="filters" role="toolbar" aria-label="Filter verdicts">
          {filters.map((item) => {
            const count = item === "ALL" ? verdicts.length : verdicts.filter((verdict) => verdict.label === item).length;
            if (item !== "ALL" && count === 0) return null;
            return (
              <button key={item} type="button" className={filter === item ? "chip chip-on" : "chip"} onClick={() => setFilter(item)}>
                {item === "ALL" ? "All" : item} {count}
              </button>
            );
          })}
        </div>
      )}
      {loading && verdicts.length === 0 && (
        <div className="skeleton" aria-hidden="true">
          <span />
          <span />
        </div>
      )}
      {!loading && verdicts.length === 0 && (
        <div className="empty-verdicts">
          <img src="/brand/empty-desk.jpg" alt="" />
          <p>Compare the proposal to see two seeded projects: one overlap, and one that only sounds similar.</p>
        </div>
      )}
      {visible.map((verdict) => {
        const open = openId === verdict.project_id;
        const known = SEEDED_PROJECTS[verdict.project_id];
        return (
          <article
            key={verdict.project_id}
            className={selectedId === verdict.project_id ? "verdict selected" : "verdict"}
            data-label={verdict.label}
            style={{ borderLeftColor: LABEL_COLOR[verdict.label] }}
          >
            <button type="button" className="verdict-select" onClick={() => onSelect(verdict.project_id)}>
              <span className="label-chip" style={{ background: LABEL_COLOR[verdict.label] }}>{verdict.label}</span>
              <span className="confidence">{Math.round(verdict.confidence * 100)}%</span>
            </button>
            <h3>{known?.name ?? verdict.project_id}</h3>
            {known && <p className="seeded-inline">Seeded for demo · not a World Bank record</p>}
            {known && <p className="why">{known.plain}</p>}
            <p className="project-id">{verdict.project_id}</p>
            <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(verdict.confidence * 100)} aria-label="Confidence">
              <span style={{ width: `${verdict.confidence * 100}%`, background: LABEL_COLOR[verdict.label] }} />
            </div>
            <p className="label-note">{LABEL_NOTE[verdict.label]}</p>
            <ul className="tags">
              {verdict.matching_attributes.map((attribute) => (
                <li key={attribute}>{attribute}</li>
              ))}
            </ul>
            <button type="button" className="text-button" aria-expanded={open} onClick={() => setOpenId(open ? null : verdict.project_id)}>
              {open ? "Hide why" : "Why this label"}
            </button>
            {open && <p className="why">{verdict.reasoning}</p>}
          </article>
        );
      })}
    </section>
  );
}
