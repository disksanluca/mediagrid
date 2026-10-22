import {AbsoluteFill, Audio, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {MediaGridVideo} from "./video";
import type {RenderOverlay, RenderProps, RenderSound} from "./types";

function KineticTitle({item}: {item: RenderOverlay}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const points = item.keyframes.map((keyframe) => Math.round(keyframe.at_ms * fps / 1000));
  const value = (key: "x" | "y" | "opacity" | "scale") => interpolate(
    frame, points, item.keyframes.map((keyframe) => keyframe[key]),
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );
  return <AbsoluteFill style={{pointerEvents: "none", zIndex: item.z_index}}>
    <div style={{
      position: "absolute", left: `${value("x") * 100}%`, top: `${value("y") * 100}%`,
      transform: `translate(-50%, -50%) scale(${value("scale")})`, opacity: value("opacity"),
      maxWidth: "88%", textAlign: "center", whiteSpace: "pre-wrap",
      color: item.color, fontSize: 72, lineHeight: 1.02, fontWeight: 900,
      fontFamily: "Arial, sans-serif", textShadow: "0 4px 20px rgba(0,0,0,.8)",
    }}>{item.text}</div>
  </AbsoluteFill>;
}

function SoundItem({item}: {item: RenderSound}) {
  const {fps} = useVideoConfig();
  return <Audio
    src={staticFile(item.media_file)}
    startFrom={Math.round((item.source_in_ms ?? 0) * fps / 1000)}
    endAt={item.source_out_ms === null ? undefined : Math.round(item.source_out_ms * fps / 1000)}
    loop={item.loop}
    volume={(frame) => {
      const at = frame * 1000 / fps;
      const fadeIn = item.fade_in_ms ? Math.min(1, at / item.fade_in_ms) : 1;
      const fadeOut = item.fade_out_ms ? Math.min(1, Math.max(0, item.duration_ms - at) / item.fade_out_ms) : 1;
      return item.gain * Math.min(fadeIn, fadeOut);
    }}
  />;
}

export function MediaGridTimelineV2(input: Partial<RenderProps>) {
  const props: RenderProps = {title:"MediaGrid",format:"vertical",accent:"#dcf769",scenes:[],overlays:[],sounds:[],...input};
  const {fps} = useVideoConfig();
  return <AbsoluteFill>
    <MediaGridVideo {...props}/>
    {(props.overlays ?? []).map((item) => <Sequence
      key={item.id}
      from={Math.round(item.start_ms * fps / 1000)}
      durationInFrames={Math.max(1, Math.round(item.duration_ms * fps / 1000))}
    ><KineticTitle item={item}/></Sequence>)}
    {(props.sounds ?? []).map((item) => <Sequence
      key={item.id}
      from={Math.round(item.start_ms * fps / 1000)}
      durationInFrames={Math.max(1, Math.round(item.duration_ms * fps / 1000))}
    ><SoundItem item={item}/></Sequence>)}
  </AbsoluteFill>;
}
