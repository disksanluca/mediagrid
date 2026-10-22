export type Engine = "football" | "geo" | "music" | "clips" | "politics" | "trends";

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
  voice_ready: boolean;
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
  transition: "impact" | "slide" | "cut" | "zoom" | "fade";
  asset_id?: string | null;
}

export interface ContentPlan {
  project_id: string;
  engine: string;
  origin?: "OUTLINE" | "BRIEF_BASED" | "OFFICIAL_SOURCE" | "LOCAL_AI" | "MANUAL";
  hook: string;
  angle: string;
  target_duration_seconds: number;
  scenes: Scene[];
  requires_fact_review: boolean;
  review_checks: string[];
  source_refs?: Array<{title:string;url:string;api_url?:string;fetched_at:string}>;
  review?: {approved_at:string;source_urls:string[];facts_confirmed:boolean;rights_confirmed:boolean;notes:string;caption?:string|null};
}

export interface OfficialProposal {
  id: number;
  number: number;
  year: number;
  summary: string;
  presented_at: string;
  source_url: string;
  api_url: string;
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

export interface Asset {
  id: string;
  name: string;
  media_type: string;
  rights_status: string;
  creator: string | null;
  license_name: string | null;
  commercial_use: boolean;
  metadata_json: {size_bytes?: number};
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
  tts: string;
  transcription: string;
}

export interface HardwareProfile {
  cpu: string;
  logical_cores: number;
  ram_gb: number | null;
  gpu: string | null;
  vram_gb: number | null;
  cuda_available: boolean;
  disk_free_gb: number;
  windows_version: string | null;
  recommended_profile: "LIGHT" | "BALANCED" | "QUALITY" | "HIGH_PERFORMANCE";
}

export interface SetupState {
  complete: boolean;
  profile: HardwareProfile["recommended_profile"] | null;
  data_dir: string;
}

export interface DoctorReport {
  checked_at: string;
  checks: Array<{id:string;name:string;status:string;detail:string}>;
}
