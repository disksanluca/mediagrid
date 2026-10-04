import {AbsoluteFill, interpolate, Sequence, spring, useCurrentFrame, useVideoConfig} from "remotion";
import type {RenderProps, RenderScene} from "./types";

const fallback: RenderProps = {
  title: "MediaGrid",
  format: "vertical",
  accent: "#c5ccd6",
  scenes: [{scene_id: "intro", duration: 3, visual_type: "headline", transition: "impact", on_screen_text: "MediaGrid"}],
};

function Scene({scene, accent, title}: {scene: RenderScene; accent: string; title: string}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 18, stiffness: 130}});
  const lineWidth = interpolate(frame, [0, fps], [0, 100], {extrapolateRight: "clamp"});
  return <AbsoluteFill style={{background: "radial-gradient(circle at 80% 15%, #1c292e, #080b0d 60%)", color: "#f5f7f8", fontFamily: "Arial, sans-serif", padding: "8%", justifyContent: "center"}}>
    <div style={{position: "absolute", top: "6%", left: "8%", fontSize: 22, letterSpacing: 8, color: accent, fontWeight: 800}}>MEDIAGRID</div>
    <div style={{height: 8, width: `${lineWidth}%`, maxWidth: 220, background: accent, marginBottom: 38}}/>
    <div style={{fontSize: 74, lineHeight: 1.02, fontWeight: 900, maxWidth: 1300, opacity: enter, transform: `translateY(${(1 - enter) * 80}px)`}}>{scene.on_screen_text ?? title}</div>
    <div style={{position: "absolute", bottom: "7%", left: "8%", fontSize: 18, color: "#8d9ba2", textTransform: "uppercase", letterSpacing: 4}}>{scene.visual_type}</div>
  </AbsoluteFill>;
}

export function MediaGridVideo(input: Partial<RenderProps>) {
  const props = {...fallback, ...input};
  const {fps} = useVideoConfig();
  let start = 0;
  return <AbsoluteFill>{props.scenes.map((scene) => {
    const durationInFrames = Math.max(1, Math.round(scene.duration * fps));
    const item = <Sequence key={scene.scene_id} from={start} durationInFrames={durationInFrames}><Scene scene={scene} accent={props.accent} title={props.title}/></Sequence>;
    start += durationInFrames;
    return item;
  })}</AbsoluteFill>;
}
