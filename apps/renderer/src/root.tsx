import {Composition} from "remotion";
import {MediaGridVideo} from "./video";
import {MediaGridTimelineV2} from "./timeline-v2";
import type {RenderProps} from "./types";

const defaults: RenderProps = {
  title: "MediaGrid",
  format: "vertical",
  accent: "#dcf769",
  scenes: [{scene_id: "intro", duration: 3, visual_type: "headline", transition: "impact", on_screen_text: "Content Operating System"}],
};

export function Root() {
  const metadata = ({props}: {props: RenderProps}) => {
    const total = props.scenes.reduce((sum, scene) => sum + scene.duration, 0);
    const dimensions = props.format === "horizontal" ? [1920, 1080] : props.format === "square" ? [1080, 1080] : [1080, 1920];
    return {durationInFrames: Math.max(1, Math.round(total * 30)), width: dimensions[0], height: dimensions[1]};
  };
  return <><Composition
    id="MediaGridVideo"
    component={MediaGridVideo}
    fps={30}
    durationInFrames={90}
    width={1080}
    height={1920}
    defaultProps={defaults}
    calculateMetadata={({props}) => metadata({props: props as unknown as RenderProps})}
  /><Composition
    id="MediaGridTimelineV2"
    component={MediaGridTimelineV2}
    fps={30}
    durationInFrames={90}
    width={1080}
    height={1920}
    defaultProps={{...defaults, overlays: []}}
    calculateMetadata={({props}) => metadata({props: props as unknown as RenderProps})}
  /></>;
}
