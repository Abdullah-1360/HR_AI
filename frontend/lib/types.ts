// lib/types.ts
export interface Job {
  id: string;
  title: string;
  description: string;
  parsed_requirements?: ParsedJob;
  created_at: string;
}

export interface ParsedJob {
  title: string;
  required_skills: string[];
  preferred_skills: string[];
  experience_years_min: number;
  seniority: string;
  responsibilities: string[];
  salary_range?: string;
  location?: string;
  work_authorization?: string;
}

export interface Candidate {
  id: string;
  name?: string;
  email?: string;
  skills?: string[];
  experience_years?: number;
  resume_url?: string;
  parsed_resume?: ParsedResume;
  created_at: string;
}

export interface ParsedResume {
  name: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  skills: string[];
  experience_years: number;
  work_history: WorkExperience[];
  education: Education[];
  projects: string[];
  certifications: string[];
  summary?: string;
}

export interface WorkExperience {
  company: string;
  role: string;
  duration: string;
  highlights: string[];
}

export interface Education {
  degree: string;
  institution: string;
  year?: number;
}

export interface MatchResult {
  overall_score: number;
  skill_match_score: number;
  experience_score: number;
  education_score: number;
  missing_skills: string[];
  strengths: string[];
  potential_risks: string[];
  reasoning: string;
  confidence: number;
  recommended_interview_focus?: string;
}

export interface RankedCandidate {
  candidate_id: string;
  name?: string;
  email?: string;
  overall_score: number;
  skill_match_score: number;
  experience_score: number;
  missing_skills: string[];
  strengths: string[];
  reasoning: string;
  confidence: number;
}

export interface MatchResponse {
  job_id: string;
  total_evaluated: number;
  ranked_candidates: RankedCandidate[];
}

export interface InterviewQuestion {
  question: string;
  category: string;
  difficulty: string;
  what_good_looks_like: string;
  follow_ups: string[];
}

export interface InterviewResponse {
  job_title: string;
  candidate_name?: string;
  technical_questions: InterviewQuestion[];
  behavioral_questions: InterviewQuestion[];
  scenario_questions: InterviewQuestion[];
  system_design_questions: InterviewQuestion[];
  evaluation_rubric: Record<string, string>;
  recommended_interview_duration_mins: number;
}

export interface PipelineResponse {
  job_id: string;
  job_title?: string;
  ranked_candidates: RankedCandidate[];
  interview_pack?: InterviewResponse;
  error?: string;
}

// Router Intelligence Types
export interface RouterOverview {
  total_requests: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  avg_latency_ms: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  active_providers: number;
  total_providers: number;
  active_models: number;
  total_models: number;
  healthy_models: number;
  active_reservations: number;
  active_reserved_tokens: number;
}

export interface ProviderTokenStat {
  provider_name: string;
  provider_key: string;
  tokens: number;
  requests: number;
}

export interface HourlyVelocity {
  timestamp: string | null;
  requests: number;
  tokens: number;
  avg_latency_ms: number;
}

export interface RouterOverviewResponse {
  overview: RouterOverview;
  by_provider: ProviderTokenStat[];
  hourly_velocity: HourlyVelocity[];
}

export interface RouterProviderCapabilities {
  streaming: boolean;
  tools: boolean;
  images: boolean;
  reasoning: boolean;
}

export interface RouterProviderMetrics {
  total_models: number;
  active_models: number;
  avg_latency_ms: number;
  error_rate: number;
  healthy: boolean;
  tokens_consumed: number;
  total_requests: number;
}

export interface RouterProvider {
  id: string;
  name: string;
  display_name: string;
  provider_type: string;
  tier: string;
  priority: number;
  enabled: boolean;
  base_url?: string;
  capabilities: RouterProviderCapabilities;
  metrics: RouterProviderMetrics;
}

export interface RouterQuota {
  type: string;
  window: string;
  limit: number;
  used: number;
  reserved: number;
  usage_percentage: number;
  window_start?: string | null;
  window_end?: string | null;
}

export interface RouterModelHealth {
  healthy: boolean;
  avg_latency_ms?: number | null;
  avg_ttft_ms?: number | null;
  error_rate: number;
  consecutive_failures: number;
  disabled_until?: string | null;
}

export interface RouterModelScores {
  overall: number;
  quality: number;
  speed: number;
  availability: number;
  cost: number;
}

export interface RouterModel {
  id: string;
  model_name: string;
  display_name: string;
  tier: string;
  enabled: boolean;
  context_window?: number;
  max_output_tokens?: number;
  capabilities: {
    vision: boolean;
    tools: boolean;
    reasoning: boolean;
    coding: boolean;
  };
  provider: {
    id: string;
    name: string;
    display_name: string;
  };
  health: RouterModelHealth;
  scores: RouterModelScores;
  last_selected_at?: string | null;
  quotas: RouterQuota[];
}

export interface RouterRequestLog {
  id: string;
  request_uuid: string;
  status: string;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  latency_ms?: number | null;
  ttft_ms?: number | null;
  http_status?: number | null;
  error_message?: string | null;
  attempt: number;
  created_at?: string | null;
  provider_name: string;
  provider_display_name: string;
  model_name: string;
  model_display_name: string;
  tier: string;
}

export interface RouterTierWaterfall {
  tier: string;
  description: string;
  request_count: number;
  total_tokens: number;
  avg_latency_ms: number;
  success_count: number;
  failure_count: number;
}

