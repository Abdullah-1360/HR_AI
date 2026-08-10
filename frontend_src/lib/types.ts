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
