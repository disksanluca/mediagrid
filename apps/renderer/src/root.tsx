import {Composition} from "remotion";
import {MediaGridVideo} from "./video";
import type {RenderProps} from "./types";

const defaults: RenderProps = {
  title: "MediaGrid",
  format: "vertical",
  accent: "#c5ccd6",
  scenes: [{scene_id: "intro", duration: 3, visual_type: "headline", transition: "impact", on_screen_text: "Content Operating System"}],
};

export function Root() {
  return <Composition
    id="MediaGridVideo"
    component={MediaGridVideo}
    fps={30}
    durationInFrames={90}
    width={1080}
    height={1920}
    defaultProps={defaults}
    calculateMetadata={({props}) => {
      const input = props as unknown as RenderProps;
      const total = input.scenes.reduce((sum, scene) => sum + scene.duration, 0);
      const dimensions = input.format === "horizontal" ? [1920, 1080] : input.format === "square" ? [1080, 1080] : [1080, 1920];
      return {durationInFrames: Math.max(1, Math.round(total * 30)), width: dimensions[0], height: dimensions[1]};
    }}
  />;
}
