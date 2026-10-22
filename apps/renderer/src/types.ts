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

