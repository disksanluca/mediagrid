import {AbsoluteFill, interpolate, Sequence, spring, useCurrentFrame, useVideoConfig} from "remotion";
import type {RenderProps, RenderScene} from "./types";

const fallback: RenderProps = {
  title: "MediaGrid",
  format: "vertical",
  accent: "#dcf769",
  scenes: [{scene_id: "intro", duration: 3, visual_type: "headline", transition: "impact", on_screen_text: "MediaGrid"}],
};

function Scene({scene, accent, title}: {scene: RenderScene; accent: string; title: string}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 18, stiffness: 130}});
  const lineWidth = interpolate(frame, [0, fps], [0, 100], {extrapolateRight: "clamp"});
  const fade = interpolate(frame, [0, Math.max(1, Math.round(fps * 0.45))], [0, 1], {extrapolateRight: "clamp"});
  const motion = {
    impact: {opacity: enter, transform: `translateY(${(1 - enter) * 80}px) scale(${1.12 - enter * 0.12})`},
    slide: {opacity: enter, transform: `translateX(${(1 - enter) * -120}px)`},
    cut: {opacity: 1, transform: "none"},
    zoom: {opacity: enter, transform: `scale(${0.72 + enter * 0.28})`},
    fade: {opacity: fade, transform: "none"},
  }[scene.transition] ?? {opacity: 1, transform: "none"};
  return <AbsoluteFill style={{background: "radial-gradient(circle at 78% 45%, #26382d, #111411 62%)", color: "#eeefe8", fontFamily: "Arial, sans-serif", padding: "8%", justifyContent: "center"}}>
    <div style={{position: "absolute", top: "6%", left: "8%", fontSize: 22, letterSpacing: 8, color: accent, fontWeight: 800}}>MEDIAGRID</div>
    <div style={{height: 4, width: `${lineWidth}%`, maxWidth: 220, background: accent, marginBottom: 38}}/>
    <div style={{fontSize: 74, lineHeight: 1.02, fontWeight: 900, maxWidth: 1300, ...motion}}>{scene.on_screen_text ?? title}</div>
    <div style={{position: "absolute", bottom: "7%", left: "8%", fontSize: 18, color: "#9aa397", textTransform: "uppercase", letterSpacing: 4}}>{scene.visual_type} / {scene.transition}</div>
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
