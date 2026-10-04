export type Engine = "football" | "geo" | "music";

export interface Channel {
  id: string;
  name: string;
  slug: string;
  niche: string;
  default_engine: Engine;
  language: string;
  timezone: string;
  autopilot_level: string;
  brand_profile: Record<string, unknown>;
  editorial_profile: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  channel_id: string;
  title: string;
  topic: string;
  content_type: string;
  format: string;
  status: string;
  plan: ContentPlan | null;
  script: Record<string, unknown> | null;
  edl: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Scene {
  id: string;
  duration_seconds: number;
  narration: string;
  visual_type: "headline" | "stat" | "map" | "image" | "quote" | "outro";
  visual_query: string;
  on_screen_text: string;
  transition: string;
}

export interface ContentPlan {
  project_id: string;
  engine: string;
  hook: string;
  angle: string;
  target_duration_seconds: number;
  scenes: Scene[];
  requires_fact_review: boolean;
}

export interface Job {
  id: string;
  project_id: string | null;
  job_type: string;
  status: string;
  progress: number;
  attempt: number;
  max_attempts: number;
  result: {output?: string} | null;
  error: string | null;
  created_at: string;
}

export interface SystemStatus {
  mode: string;
  paid_ai_allowed: boolean;
  database: string;
  ffmpeg: boolean;
  ollama: "CONNECTED" | "NOT_CONNECTED";
  dry_run: boolean;
  engines: string[];
}
