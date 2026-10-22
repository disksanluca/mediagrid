export interface RenderScene {
  scene_id: string;
  duration: number;
  visual_type: string;
  transition: "impact" | "slide" | "cut" | "zoom" | "fade";
  on_screen_text?: string;
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
  scenes: RenderScene[];
  overlays?: RenderOverlay[];
  sounds?: RenderSound[];
  video_layers?: RenderVideoLayer[];
}

export interface RenderOverlay {
  id: string;
  start_ms: number;
  duration_ms: number;
  z_index: number;
  text: string;
  color: string;
  keyframes: Array<{
    at_ms: number;
    x: number;
    y: number;
    opacity: number;
    scale: number;
  }>;
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

