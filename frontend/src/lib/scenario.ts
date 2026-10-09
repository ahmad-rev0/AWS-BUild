import type { ProposalCreate } from "../types/api";

export const DEMO_PROPOSAL_ID = "demo-proposal-01";
export const HIGH_NEED_DISTRICT_ID = "atlas11-demo-district-high";

export const SEEDED_PROJECTS: Record<string, { name: string; plain: string }> = {
  "seeded-demo-transit-corridor": {
    name: "Existing transit corridor",
    plain: "Same district, same commuters, same years. This one overlaps, so the teams should coordinate.",
  },
  "seeded-demo-accessibility-link": {
    name: "Feeder-route accessibility link",
    plain: "It sounds similar, but it is a different route. It complements the corridor. It is not a duplicate.",
  },
};

export const CANONICAL_PROPOSAL: ProposalCreate = {
  title: "Demo City accessible transit corridor",
  description:
    "Seeded demonstration proposal for accessible bus corridor stops serving commuters in the high-need district.",
  city_id: "atlas11-demo-city",
  district_id: "atlas11-demo-district-high",
  sector: "Urban Transport",
  budget_usd: "24000000",
  start_date: "2026-01-01",
  end_date: "2028-12-31",
  scenario_key: "demo-city-transit-01",
  source: "seeded",
  source_url: "seeded://atlas11/demo-city-transit-01",
};

const fields = Object.keys(CANONICAL_PROPOSAL) as (keyof ProposalCreate)[];

export function isCanonical(draft: ProposalCreate): boolean {
  return fields.every((field) => draft[field] === CANONICAL_PROPOSAL[field]);
}
