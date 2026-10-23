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

export interface FootballShot {
  asset_id: string;
  source_sha256?: string;
  in_ms: number;
  out_ms: number;
  role: "build_up" | "action" | "reaction" | "replay" | "celebration";
  verified_event_id: string | null;
  focus_x: number;
  focus_y: number;
}

export interface FootballSequence {
  id: string;
  project_id: string;
  revision: number;
  status: "REVIEW_REQUIRED" | "APPROVED";
  aspect: "horizontal" | "vertical";
  shots: FootballShot[];
  score_label: string | null;
  score_source_url: string | null;
}

export interface Narrative3DShot {
  duration_ms: number;
  beat_text: string;
  action: "notice" | "reach" | "react" | "celebrate";
  camera: "wide" | "medium" | "close";
  lighting: "calm" | "tense" | "bright";
}

export interface Narrative3DSequence {
  id: string;
  project_id: string;
  revision: number;
  status: "REVIEW_REQUIRED" | "APPROVED";
  title: string;
  aspect: "vertical" | "horizontal";
  shots: Narrative3DShot[];
  rig_version: string;
  world_version: string;
  audio_asset_id: string | null;
  audio_sha256: string | null;
  blocking_job_id: string | null;
  blocking_sha256: string | null;
  story_sha256: string;
  blender_available?: boolean;
}

export interface KnowledgeClaim {
  id: string;
  project_id: string;
  scene_id: string;
  text: string;
  source_url: string;
  source_title: string;
  published_at: string;
  support_excerpt: string;
  revision: number;
  status: "REVIEW_REQUIRED" | "APPROVED" | "REMOVED";
  reviewed_at: string | null;
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
  clip_start_seconds?: number;
  clip_end_seconds?: number | null;
}

export interface TimelineItem {
  id: string;
  start_ms: number;
  duration_ms: number;
  z_index: number;
  source_asset_id?: string | null;
  source_in_ms?: number | null;
  source_out_ms?: number | null;
  speed: number;
  preset?: string | null;
  params: {scene_id?: string; text?: string; [key: string]: unknown};
}

export interface TimelineResponse {
  revision: number;
  legacy_sha256: string;
  renderer: string;
  edl: {
    version: 2;
    revision: number;
    canvas: {width:number;height:number;fps_num:number;fps_den:number};
    duration_ms: number;
    tracks: Array<{id: string; kind: string; items: TimelineItem[]}>;
  };
}

export interface PreviewResponse {
  revision: number;
  revision_sha256: string;
  duration_seconds: number;
  voice_ready: boolean;
  props: import("../../renderer/src/types").RenderProps;
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
  source_refs?: Array<{title:string;url:string;api_url?:string;fetched_at:string;source_sha256?:string}>;
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

export interface GeoMunicipality {
  id: number;
  name: string;
  state_code: string;
  state_name: string;
  region_name: string;
  immediate_name: string;
  intermediate_name: string;
  source_url: string;
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
  source_url: string | null;
  creator: string | null;
  license_name: string | null;
  commercial_use: boolean;
  metadata_json: {size_bytes?: number;duration_ms?:number;video_codec?:string;audio_codec?:string|null;proxy_sha256?:string;proxy_duration_ms?:number;waveform_sha256?:string|null;waveform_status?:string;ingest_status?:string};
  created_at: string;
}

export interface TranscriptWord {
  start_ms:number; end_ms:number; text:string;
  confidence:number|null; speaker_id:string|null; edited:boolean;
}

export interface CaptionCue {
  start_ms:number; end_ms:number; text:string; speaker_id:string|null;
}

export interface TimedTranscript {
  asset_id:string; source_sha256:string; engine:string;
  model_id:string; model_version:string; language:string;
  revision:number; status:string; words:TranscriptWord[]; cues:CaptionCue[];
}

export interface ClipCandidate {
  id:string; asset_id:string; source_sha256:string; source_url:string|null;
  transcript_revision:number; analysis_version:string;
  start_ms:number; end_ms:number; context_start_ms:number; context_end_ms:number;
  word_start_index:number; word_end_index:number; score:number; reason_codes:string[];
  status:string; selected_start_ms:number|null; selected_end_ms:number|null;
  aspect:"source"|"vertical"; focus_x:number; focus_y:number; revision:number;
  context_before:string; spoken_text:string; context_after:string;
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
