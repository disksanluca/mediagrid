export interface RenderScene {
  scene_id: string;
  duration: number;
  visual_type: string;
  transition: string;
  on_screen_text?: string;
}

export interface RenderProps {
  title: string;
  format: "horizontal" | "vertical" | "square";
  accent: string;
  scenes: RenderScene[];
}

