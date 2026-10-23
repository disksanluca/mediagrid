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

function MotionCard({item}: {item: RenderOverlay}) {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const points = item.keyframes.map((keyframe) => Math.round(keyframe.at_ms * fps / 1000));
  const value = (key: "x" | "y" | "opacity" | "scale") => interpolate(
    frame, points, item.keyframes.map((keyframe) => keyframe[key]),
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );
  const unit = width / 1080;
  const horizontal = width > height;
  const split = item.layout === "split" && horizontal;
  return <AbsoluteFill style={{pointerEvents: "none", zIndex: item.z_index,
    background: "rgba(7, 15, 16, .68)", color: "#f5f7f2", fontFamily: "Arial, sans-serif"}}>
    <div style={{position: "absolute", left: `${value("x") * 100}%`,
      top: `${value("y") * 100}%`, width: "82%", maxWidth: horizontal ? 1380 : 900,
      transform: `translate(-50%, -50%) scale(${value("scale")})`,
      opacity: value("opacity"), boxSizing: "border-box", overflow: "hidden",
      border: `2px solid ${item.color}`, borderRadius: 28 * unit,
      background: "#101a18", boxShadow: "0 30px 100px #0009"}}>
      <div style={{height: 14 * unit, background: item.color}} />
      <div style={{padding: `${Math.max(28, 46 * unit)}px`,
        display: split ? "grid" : "block", gridTemplateColumns: split ? "1fr 2fr" : undefined,
        gap: split ? 36 * unit : undefined}}>
        <div style={{color: item.color, fontSize: 25 * unit, fontWeight: 800,
          letterSpacing: 4 * unit, marginBottom: 24 * unit, overflowWrap: "anywhere"}}>{item.label}</div>
        <div><div style={{fontSize: (horizontal ? 72 : 82) * unit,
          lineHeight: 1.02, fontWeight: 900, overflowWrap: "anywhere"}}>{item.text}</div>
          <div style={{marginTop: 32 * unit, fontSize: 34 * unit,
            lineHeight: 1.24, color: "#c3cec8", overflowWrap: "anywhere"}}>{item.body}</div></div>
      </div>
    </div>
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
    >{item.preset === "motion_card_v1" ? <MotionCard item={item}/> : <KineticTitle item={item}/>}</Sequence>)}
    {(props.sounds ?? []).map((item) => <Sequence
      key={item.id}
      from={Math.round(item.start_ms * fps / 1000)}
      durationInFrames={Math.max(1, Math.round(item.duration_ms * fps / 1000))}
    ><SoundItem item={item}/></Sequence>)}
    {props.voice_file && <Audio src={mediaSource(props.voice_file)}/>}
  </AbsoluteFill>;
}
