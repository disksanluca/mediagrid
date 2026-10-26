export interface RenderScene {
  scene_id: string;
  duration: number;
  visual_type: string;
  transition: "impact" | "slide" | "cut" | "zoom" | "fade";
  on_screen_text?: string;
  supporting_text?: string;
  asset_id?: string | null;
  media_kind?: "image" | "video";
  media_file?: string;
  media_duration?: number;
  clip_start_seconds?: number;
  clip_end_seconds?: number | null;
}

export interface RenderProps {
  title: string;
  format: "horizontal" | "vertical" | "square";
  accent: string;
  source_label?: string | null;
  editorial_style?: "official_politics" | "wikimedia_trends" | "musicbrainz_metadata";
  official_reference?: string;
  source_checked_at?: string;
  wiki_article?: string;
  wiki_views?: number;
  wiki_rank?: number;
  wiki_observed_on?: string;
  music_title?: string;
  music_artist?: string;
  music_first_release_date?: string;
  music_record_id?: string;
  scenes: RenderScene[];
  overlays?: (RenderOverlay | MotionRenderOverlay)[];
  sounds?: RenderSound[];
  video_layers?: RenderVideoLayer[];
  voice_file?: string;
}

export interface RenderOverlay {
  id: string;
  preset?: "kinetic_title_v1" | "motion_card_v1" | "flow_path_v1" | "character_dialogue_v1" | "sports_cinematic_v1";
  phase?: "impact" | "reveal" | "play" | "resolve";
  background?: string;
  paper?: string;
  font_display?: string;
  art_direction?: "original" | "editorial" | "broadcast" | "broadcast_final";
  diagnostics?: boolean;
  start_ms: number;
  duration_ms: number;
  z_index: number;
  text: string;
  color: string;
  label?: string;
  body?: string;
  layout?: "stack" | "split";
  steps?: string[];
  source_label?: string | null;
  character_id?: "migo_v1" | "luma_v1";
  expression?: "neutral" | "happy" | "skeptical" | "surprised";
  pose?: "idle" | "point" | "shrug";
  mouth_cues?: Array<{start_ms:number;end_ms:number;viseme:"closed"|"open"|"round"|"smile"}>;
  partner_character_id?: "migo_v1" | "luma_v1" | null;
  partner_text?: string | null;
  partner_color?: string | null;
  partner_expression?: "neutral" | "happy" | "skeptical" | "surprised" | null;
  partner_pose?: "idle" | "point" | "shrug" | null;
  partner_mouth_cues?: Array<{start_ms:number;end_ms:number;viseme:"closed"|"open"|"round"|"smile"}> | null;
  keyframes: Array<{
    at_ms: number;
    x: number;
    y: number;
    opacity: number;
    scale: number;
  }>;
}

export type MotionRenderOverlay = import("./motion-scene").MotionOverlay & {
  preset: "motion_scene_v1";
}

export interface RenderSound {
  id: string;
  start_ms: number;
  duration_ms: number;
  media_file: string;
  source_in_ms: number | null;
  source_out_ms: number | null;
  gain: number;
  fade_in_ms: number;
  fade_out_ms: number;
  loop: boolean;
}

export interface RenderVideoLayer {
  id: string;
  start_ms: number;
  duration_ms: number;
  z_index: number;
  media_file: string;
  source_in_ms: number;
  source_out_ms: number;
  focus_x: number;
  focus_y: number;
  opacity: number;
}

