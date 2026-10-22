import {AbsoluteFill, Img, OffthreadVideo, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import type {RenderProps, RenderScene} from "./types";

const fallback: RenderProps = {
  title: "MediaGrid",
  format: "vertical",
  accent: "#dcf769",
  scenes: [{scene_id: "intro", duration: 3, visual_type: "headline", transition: "impact", on_screen_text: "MediaGrid"}],
};

function Scene({scene, accent, title, sourceLabel}: {scene: RenderScene; accent: string; title: string; sourceLabel?: string | null}) {
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
    {scene.media_file && scene.media_kind === "image" && <Img src={staticFile(scene.media_file)} style={{position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover"}}/>}
    {scene.media_file && scene.media_kind === "video" && scene.media_duration && <Sequence from={0} durationInFrames={Math.max(1, Math.floor(((scene.clip_end_seconds ?? scene.media_duration) - (scene.clip_start_seconds ?? 0)) * fps) - 1)} loop><OffthreadVideo src={staticFile(scene.media_file)} startFrom={Math.round((scene.clip_start_seconds ?? 0) * fps)} muted style={{position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover"}}/></Sequence>}
    {scene.media_file && <AbsoluteFill style={{background: "linear-gradient(90deg, rgba(8,12,10,.88), rgba(8,12,10,.49) 75%, rgba(8,12,10,.3))"}}/>}
    <div style={{position: "absolute", top: "6%", left: "8%", fontSize: 22, letterSpacing: 8, color: accent, fontWeight: 800}}>MEDIAGRID</div>
    <div style={{height: 4, width: `${lineWidth}%`, maxWidth: 220, background: accent, marginBottom: 38}}/>
    <div style={{fontSize: 74, lineHeight: 1.02, fontWeight: 900, maxWidth: 1300, ...motion}}>{scene.on_screen_text ?? title}</div>
    {sourceLabel && <div style={{position: "absolute", bottom: "7%", left: "8%", fontSize: 22, color: "#aab4a7", letterSpacing: 1.5}}>{sourceLabel}</div>}
  </AbsoluteFill>;
}

export function MediaGridVideo(input: Partial<RenderProps>) {
  const props = {...fallback, ...input};
  const {fps} = useVideoConfig();
  let start = 0;
  return <AbsoluteFill>{props.scenes.map((scene) => {
    const durationInFrames = Math.max(1, Math.round(scene.duration * fps));
    const item = <Sequence key={scene.scene_id} from={start} durationInFrames={durationInFrames}><Scene scene={scene} accent={props.accent} title={props.title} sourceLabel={props.source_label}/></Sequence>;
    start += durationInFrames;
    return item;
  })}</AbsoluteFill>;
}
