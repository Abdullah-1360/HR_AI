// lib/api.ts
import axios from 'axios';
import type {
  Job, Candidate, MatchResponse, InterviewResponse, PipelineResponse
} from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 120000,
});

export const api = {
  jobs: {
    create: async (title: string, rawDescription: string): Promise<Job> => {
      const { data } = await client.post('/jobs/', { title, raw_description: rawDescription });
      return data;
    },
    list: async (limit = 50, offset = 0): Promise<{ items: Job[]; total: number }> => {
      const { data } = await client.get('/jobs/', { params: { limit, offset } });
      return data;
    },
    get: async (id: string): Promise<Job> => {
      const { data } = await client.get(`/jobs/${id}`);
      return data;
    },
  },

  candidates: {
    upload: async (file: File): Promise<Candidate> => {
      const form = new FormData();
      form.append('file', file);
      const { data } = await client.post('/candidates/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return data;
    },
    list: async (limit = 50, offset = 0): Promise<{ items: Candidate[]; total: number }> => {
      const { data } = await client.get('/candidates/', { params: { limit, offset } });
      return data;
    },
    get: async (id: string): Promise<Candidate> => {
      const { data } = await client.get(`/candidates/${id}`);
      return data;
    },
  },

  hiring: {
    match: async (jobId: string, topK = 20): Promise<MatchResponse> => {
      const { data } = await client.post('/hiring/match', { job_id: jobId, top_k: topK });
      return data;
    },
    getMatches: async (jobId: string): Promise<MatchResponse> => {
      const { data } = await client.get(`/hiring/matches/${jobId}`);
      return data;
    },
    interview: async (jobId: string, candidateId: string): Promise<InterviewResponse> => {
      const { data } = await client.post('/hiring/interview', { job_id: jobId, candidate_id: candidateId });
      return data;
    },
    pipeline: async (jobId: string, topK = 20): Promise<PipelineResponse> => {
      const { data } = await client.post('/hiring/pipeline', { job_id: jobId, top_k: topK });
      return data;
    },
  },

  health: async () => {
    const { data } = await axios.get(`${BASE_URL}/health`);
    return data;
  },
};
