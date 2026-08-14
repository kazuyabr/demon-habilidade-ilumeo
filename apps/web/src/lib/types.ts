// Shared types mirroring the RiskLens API schemas.

export type Role = "admin" | "analyst" | "viewer";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
}

export type DocStatus = "pending" | "processing" | "completed" | "failed";

export interface DocumentItem {
  id: string;
  filename: string;
  title: string;
  content_type: string;
  status: DocStatus;
  error_message: string | null;
  source: string | null;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface UploadResponse {
  document: DocumentItem;
  duplicate: boolean;
}

export interface Extraction {
  id: string;
  document_id: string;
  schema_name: string;
  status: string;
  data: Record<string, unknown> | null;
  model_used: string | null;
  confidence: number | null;
  error_message: string | null;
  created_at: string;
}

export interface Citation {
  index: number;
  document_id: string;
  document_title: string;
  snippet: string;
  score: number;
}

export interface RagAnswer {
  question: string;
  answer: string;
  citations: Citation[];
  grounded: boolean;
}

export interface AgentStep {
  kind: string;
  thought: string | null;
  action: string | null;
  action_input: string | null;
  observation: string | null;
  output: string | null;
  ts: string;
}

export interface AgentRun {
  id: string;
  question: string;
  status: string;
  result: Record<string, unknown> | null;
  trace: AgentStep[];
  model_used: string | null;
  error_message: string | null;
  created_at: string;
}

export interface EvalRun {
  id: string;
  name: string;
  status: string;
  model_used: string | null;
  metrics: Record<string, unknown> | null;
  items: Array<Record<string, unknown>>;
  error_message: string | null;
  created_at: string;
}

export interface FeatureFlags {
  agent_review_enabled: boolean;
  rag_hybrid_search: boolean;
  eval_llm_judge: boolean;
  llm_model: string;
  llm_provider: string;
  embedding_model: string;
  embedding_provider: string;
  embedding_dims: number;
}

export const STATUS_COLORS: Record<string, string> = {
  pending: "bg-zinc-400",
  processing: "bg-blue-500 animate-pulse",
  completed: "bg-emerald-500",
  completed_with_failures: "bg-amber-500",
  failed: "bg-red-500",
  running: "bg-blue-500 animate-pulse",
};

// --- structured extraction (credit_report schema) ---

export interface KeyMetric {
  name: string;
  value: string;
  unit?: string | null;
  period?: string | null;
}

export interface CreditFactor {
  factor: string;
  assessment?: string | null;
  severity: string;
  notes?: string | null;
}

export interface RedFlag {
  flag: string;
  severity: string;
  evidence?: string | null;
}

export interface FinancialHealth {
  revenue?: string | null;
  net_profit?: string | null;
  total_debt?: string | null;
  liquidity_ratio?: string | null;
  debt_to_equity?: string | null;
}

export interface CreditReportData {
  company_name?: string;
  sector?: string;
  analysis_date?: string | null;
  overall_risk_score?: number;
  risk_rating?: string;
  decision?: string;
  decision_justification?: string;
  confidence?: number;
  recommended_limit?: string | null;
  key_metrics?: KeyMetric[];
  credit_factors?: CreditFactor[];
  red_flags?: RedFlag[];
  financial_health?: FinancialHealth;
}

export interface EvalItemMetrics {
  decision_match?: boolean;
  fuzzy?: number;
  redflag_recall?: number;
  score_mae?: number | null;
}

export interface EvalItem {
  case?: string;
  status?: string;
  error?: string;
  metrics?: EvalItemMetrics;
  actual?: Record<string, unknown>;
}
