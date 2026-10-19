export interface RenderScene {
  scene_id: string;
  duration: number;
  visual_type: string;
  transition: "impact" | "slide" | "cut" | "zoom" | "fade";
  on_screen_text?: string;
}

export interface RenderProps {
  title: string;
  format: "horizontal" | "vertical" | "square";
  accent: string;
  source_label?: string | null;
  scenes: RenderScene[];
}

