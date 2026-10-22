import {AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, useCurrentFrame, useVideoConfig} from "remotion";
import {MediaGridVideo} from "./video";
import type {RenderOverlay, RenderProps, RenderSound, RenderVideoLayer} from "./types";
import {mediaSource} from "./media-source";

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
    src={mediaSource(item.media_file)}
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

function VideoLayer({item}: {item: RenderVideoLayer}) {
  const {fps} = useVideoConfig();
  return <AbsoluteFill style={{pointerEvents:"none",opacity:item.opacity}}>
    <OffthreadVideo muted src={mediaSource(item.media_file)}
      trimBefore={Math.round(item.source_in_ms * fps / 1000)}
      style={{width:"100%",height:"100%",objectFit:"cover",objectPosition:`${item.focus_x*100}% ${item.focus_y*100}%`}}
    />
  </AbsoluteFill>;
}

export function MediaGridTimelineV2(input: Partial<RenderProps>) {
  const props: RenderProps = {title:"MediaGrid",format:"vertical",accent:"#dcf769",scenes:[],overlays:[],sounds:[],video_layers:[],...input};
  const {fps} = useVideoConfig();
  return <AbsoluteFill>
    <MediaGridVideo {...props}/>
    {[...(props.video_layers ?? [])].sort((a,b)=>a.z_index-b.z_index).map((item)=><Sequence
      key={item.id}
      from={Math.round(item.start_ms * fps / 1000)}
      durationInFrames={Math.max(1,Math.round(item.duration_ms * fps / 1000))}
    ><VideoLayer item={item}/></Sequence>)}
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
    {props.voice_file && <Audio src={mediaSource(props.voice_file)}/>}
  </AbsoluteFill>;
}
