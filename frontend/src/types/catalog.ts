export interface CatalogProject {
  project_id: string;
  name: string;
  funder: string;
  country: string;
  city: string | null;
  sector: string;
  amount_usd: string;
  status: string | null;
  source: string;
  source_url: string | null;
  description: string;
}

export interface CatalogCity {
  city: string;
  country: string;
  project_count: number;
}

export interface CatalogSummary {
  source: string;
  projects_api: string;
  project_count: number;
  projects_without_city: number;
  countries: { country: string; project_count: number }[];
  cities: CatalogCity[];
}

export interface CatalogCompareRequest {
  title: string;
  description: string;
  country: string;
  city: string;
  sector: string;
}

export interface CatalogMatch {
  project: CatalogProject;
  label: string;
  score: number;
  shared_terms: string[];
  same_city: boolean;
  explanation: string;
}

export interface CatalogCompareResponse {
  matches: CatalogMatch[];
  note: string;
}

export interface AreaOption {
  country: string;
  city: string;
  project_count: number;
  worldbank_usd: string;
  relevance: number;
  nearest_project_id: string | null;
  nearest_project_name: string | null;
  nearest_source_url: string | null;
  recommended: boolean;
  reason: string;
}

export interface CatalogRecommendation {
  country: string;
  recommended_city: string;
  call: string;
  summary: string;
  note: string;
  areas: AreaOption[];
  model_id?: string;
}

export interface CatalogCommitRequest {
  country: string;
  city: string;
  title: string;
  amount_usd: string;
  project_ids: string[];
  recommended_city?: string | null;
  human_choice?: "accepted" | "override" | "unreviewed";
  decision_note?: string;
}

export interface ProjectImpact {
  project_id: string;
  name: string;
  source_url: string | null;
  label: string;
  worldbank_amount_usd: string;
  added_usd: string;
  combined_usd: string;
  connection: string;
}

export interface FundingImpact {
  worldbank_in_city_usd: string;
  added_usd: string;
  after_usd: string;
  lines: ProjectImpact[];
}

export interface CatalogCommitment {
  commitment_id: string;
  country: string;
  city: string;
  title: string;
  amount_usd: string;
  project_ids: string[];
  created_at: string;
  projects: CatalogProject[];
  impact: FundingImpact;
  recommended_city?: string | null;
  human_choice?: string;
  decision_note?: string;
}
