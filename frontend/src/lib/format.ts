import type { Recommendation, Verdict, VerdictLabel } from "../types/api";

export const LABEL_COLOR: Record<VerdictLabel, string> = {
  DUPLICATE: "#C0392B",
  OVERLAPPING: "#D68910",
  COMPLEMENTARY: "#138D75",
  UNRELATED: "#7F8C8D",
};

export const LABEL_NOTE: Record<VerdictLabel, string> = {
  DUPLICATE: "Same outputs, place, and period",
  OVERLAPPING: "Shared place, period, or beneficiaries",
  COMPLEMENTARY: "Related work that does not copy outputs",
  UNRELATED: "No material coordination clash",
};

export const RECOMMENDATION_LABEL: Record<Recommendation, string> = {
  MERGE: "Merge coordination",
  CO_FINANCE: "Co-finance coordination",
  PROCEED: "Proceed",
  REDIRECT: "Redirect coordination focus",
};

export function formatMoney(value: string | number): string {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "US$—";
  const sign = amount < 0 ? "-" : "";
  const absolute = Math.abs(amount);
  if (absolute >= 1_000_000_000) return `${sign}US$${trim(absolute / 1_000_000_000)}B`;
  if (absolute >= 1_000_000) return `${sign}US$${trim(absolute / 1_000_000)}M`;
  if (absolute >= 10_000) return `${sign}US$${trim(absolute / 1_000)}K`;
  return `${sign}US$${absolute.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function formatWhen(value: string | undefined): string {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function needColor(score: number): string {
  const t = Math.min(1, Math.max(0, score));
  const from = [228, 236, 232];
  const to = [14, 70, 82];
  const mixed = from.map((channel, index) => Math.round(channel + ((to[index] ?? channel) - channel) * t));
  return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
}

export function eventLine(event: { type: string; name?: string | null; ms?: number | null; payload?: Record<string, unknown> | null }): string {
  const message = typeof event.payload?.message === "string" ? event.payload.message : "";
  if (event.type === "tool_call") {
    const duration = typeof event.ms === "number" ? ` · ${event.ms} ms` : "";
    return `${message || event.name || "Tool call"}${duration}`;
  }
  if (event.type === "verdict") {
    const label = typeof event.payload?.label === "string" ? event.payload.label : "verdict";
    return `Recorded ${label} verdict`;
  }
  if (event.type === "done") return "Validated report is ready.";
  if (event.type === "error") return message || "The review stream reported an error.";
  return message || "Working…";
}

export function isVerdict(value: Record<string, unknown> | null | undefined): boolean {
  if (!value) return false;
  const label = value.label;
  const labels: VerdictLabel[] = ["DUPLICATE", "OVERLAPPING", "COMPLEMENTARY", "UNRELATED"];
  return (
    typeof value.project_id === "string" &&
    typeof label === "string" &&
    labels.includes(label as VerdictLabel) &&
    typeof value.confidence === "number" &&
    Number.isFinite(value.confidence) &&
    value.confidence >= 0 &&
    value.confidence <= 1 &&
    typeof value.reasoning === "string" &&
    value.reasoning.trim().length > 0 &&
    Array.isArray(value.matching_attributes) &&
    value.matching_attributes.every((item) => typeof item === "string")
  );
}

function trim(value: number): string {
  return value.toFixed(value >= 10 ? 0 : 1).replace(/\.0$/, "");
}
