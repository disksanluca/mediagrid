import {AbsoluteFill, interpolate, Sequence, useCurrentFrame, useVideoConfig} from "remotion";
import {MediaGridVideo} from "./video";
import type {RenderOverlay, RenderProps} from "./types";

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

export function MediaGridTimelineV2(input: Partial<RenderProps>) {
  const props: RenderProps = {title:"MediaGrid",format:"vertical",accent:"#dcf769",scenes:[],overlays:[],...input};
  const {fps} = useVideoConfig();
  return <AbsoluteFill>
    <MediaGridVideo {...props}/>
    {(props.overlays ?? []).map((item) => <Sequence
      key={item.id}
      from={Math.round(item.start_ms * fps / 1000)}
      durationInFrames={Math.max(1, Math.round(item.duration_ms * fps / 1000))}
    ><KineticTitle item={item}/></Sequence>)}
  </AbsoluteFill>;
}
