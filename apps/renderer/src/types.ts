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
}

export interface RenderProps {
  title: string;
  format: "horizontal" | "vertical" | "square";
  accent: string;
  source_label?: string | null;
  scenes: RenderScene[];
}

