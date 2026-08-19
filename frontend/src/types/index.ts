export type HealthStatus = "healthy" | "running" | "repairing" | "failed" | "paused";

export interface ProductCurrentValue {
  price: number | null;
  currency: string | null;
  availability: string | null;
  rating: number | null;
  reviews_count: number | null;
  snapshot_id: string | null;
  captured_at: string | null;
}

export interface WatchSummary {
  id: string;
  user_id: string;
  url: string;
  title: string;
  domain: string;
  status: "active" | "paused" | "archived";
  cadence_minutes: number;
  timezone: string;
  health_status: HealthStatus;
  latest_successful_run_at: string | null;
  latest_value: ProductCurrentValue | null;
  created_at: string;
  updated_at: string;
}

export interface WatchRule {
  type: "price_below" | "price_above" | "price_drop" | "availability_changed" | "back_in_stock";
  field: string;
  value?: number | null;
  currency?: string | null;
}

export interface MonitoringSpec {
  vertical: string;
  rules: WatchRule[];
  currency?: string;
  cadence_minutes?: number;
  collector_id?: string;
  [key: string]: any;
}

export interface Schedule {
  id?: string;
  cadence: "hourly" | "daily" | "weekly" | "custom";
  timezone: string;
  next_due_at?: string;
  enabled?: boolean;
}

export interface Watch {
  id: string;
  user_id: string;
  url: string;
  title: string;
  instruction: string;
  monitoring_spec: MonitoringSpec;
  status: "active" | "paused" | "archived";
  created_at: string;
  updated_at: string;
  schedule: Schedule;
}

export interface Snapshot {
  id: string;
  run_id: string;
  watch_id: string;
  payload: {
    url?: string;
    title?: string;
    price?: number | null;
    currency?: string | null;
    availability?: string | null;
    seller?: string | null;
    rating?: number | null;
    reviews_count?: number | null;
    [key: string]: any;
  };
  captured_at: string;
}

export interface WatchRun {
  id: string;
  watch_id: string;
  scheduled_for: string;
  status: "pending" | "running" | "succeeded" | "failed";
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  bright_data_collection_id: string | null;
  created_at: string;
}

export interface AlertEvent {
  id: string;
  watch_id: string;
  run_id: string | null;
  event_type: string;
  summary: string;
  details: Record<string, any>;
  status: string;
  created_at: string;
  watch_title?: string;
  watch_url?: string;
}

export interface ScraperRepair {
  id: string;
  watch_id: string;
  run_id: string;
  collector_id: string;
  repair_prompt: string;
  status: "pending" | "in_progress" | "resolved" | "failed";
  attempt_count: number;
  last_attempt_at: string | null;
  resolved_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface WatchOverviewStats {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  total_events: number;
}

export interface WatchOverview {
  watch: Watch;
  health_status: HealthStatus;
  latest_snapshot: Snapshot | null;
  latest_run: WatchRun | null;
  latest_event: AlertEvent | null;
  active_repair: ScraperRepair | null;
  latest_value: ProductCurrentValue | null;
  stats: WatchOverviewStats;
}

export interface WatchPlanSchedule {
  cadence: "hourly" | "daily" | "weekly" | "custom";
  cadence_minutes?: number;
  timezone: string;
}

export interface WatchPlan {
  url: string;
  title: string;
  intent: string;
  schedule: WatchPlanSchedule;
  monitoring_spec: MonitoringSpec;
  collector_id: string;
}

export interface WatchPlanClarification {
  reason: string;
  question: string;
  missing: string[];
}

export interface WatchPlanPreviewResponse {
  status: "ready" | "needs_clarification" | "unsupported";
  plan: WatchPlan | null;
  clarification: WatchPlanClarification | null;
  message: string;
}

export interface WatchUpdateInput {
  title?: string;
  instruction?: string;
  monitoring_spec?: MonitoringSpec;
  schedule?: {
    cadence?: "hourly" | "daily" | "weekly" | "custom";
    timezone?: string;
    next_due_at?: string;
    enabled?: boolean;
  };
  status?: "active" | "paused" | "archived";
}

export interface User {
  id: string;
  email: string;
  created_at: string;
  updated_at: string;
}
