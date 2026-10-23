import {AbsoluteFill, Img, OffthreadVideo, interpolate, Sequence, spring, useCurrentFrame, useVideoConfig} from "remotion";
import type {RenderProps, RenderScene} from "./types";
import {mediaSource} from "./media-source";

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
    <SceneMedia scene={scene} fps={fps}/>
    {scene.media_file && <AbsoluteFill style={{background: "linear-gradient(90deg, rgba(8,12,10,.88), rgba(8,12,10,.49) 75%, rgba(8,12,10,.3))"}}/>}
    <div style={{position: "absolute", top: "6%", left: "8%", fontSize: 22, letterSpacing: 8, color: accent, fontWeight: 800}}>MEDIAGRID</div>
    <div style={{height: 4, width: `${lineWidth}%`, maxWidth: 220, background: accent, marginBottom: 38}}/>
    <div style={{fontSize: 74, lineHeight: 1.02, fontWeight: 900, maxWidth: 1300, ...motion}}>{scene.on_screen_text ?? title}</div>
    {sourceLabel && <div style={{position: "absolute", bottom: "7%", left: "8%", fontSize: 22, color: "#aab4a7", letterSpacing: 1.5}}>{sourceLabel}</div>}
  </AbsoluteFill>;
}

function SceneMedia({scene,fps}:{scene:RenderScene;fps:number}) {
  return <>
    {scene.media_file&&scene.media_kind==="image"&&<Img src={mediaSource(scene.media_file)} style={{position:"absolute",inset:0,width:"100%",height:"100%",objectFit:"cover"}}/>}
    {scene.media_file&&scene.media_kind==="video"&&scene.media_duration&&<Sequence from={0} durationInFrames={Math.max(1,Math.floor(((scene.clip_end_seconds??scene.media_duration)-(scene.clip_start_seconds??0))*fps)-1)} loop><OffthreadVideo src={mediaSource(scene.media_file)} startFrom={Math.round((scene.clip_start_seconds??0)*fps)} muted style={{position:"absolute",inset:0,width:"100%",height:"100%",objectFit:"cover"}}/></Sequence>}
  </>;
}

function OfficialPoliticsScene({scene,accent,title,sourceLabel,reference,checkedAt,index,total}:{scene:RenderScene;accent:string;title:string;sourceLabel?:string|null;reference?:string;checkedAt?:string;index:number;total:number}) {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const enter=spring({frame,fps,config:{damping:22,stiffness:130}});
  const progress=Math.min(1,frame/Math.max(1,Math.round(scene.duration*fps)));
  const text=scene.on_screen_text||title;
  const kicker=scene.visual_type==="headline"?"REGISTRO OFICIAL":scene.visual_type==="quote"?"EMENTA DO PROJETO":"DADOS DO REGISTRO";
  const date=checkedAt&&/^\d{4}-\d{2}-\d{2}$/.test(checkedAt)?`${checkedAt.slice(8,10)}/${checkedAt.slice(5,7)}/${checkedAt.slice(0,4)}`:null;
  return <AbsoluteFill style={{background:"radial-gradient(circle at 86% 35%, #1d2a21, #0B0E0C 62%)",color:"#F1F3ED",fontFamily:"system-ui, sans-serif",overflow:"hidden"}}>
    <SceneMedia scene={scene} fps={fps}/>
    {scene.media_file&&<AbsoluteFill style={{background:"linear-gradient(90deg,rgba(11,14,12,.95),rgba(11,14,12,.62))"}}/>}
    <div style={{position:"absolute",top:103,left:86,right:86,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
      <span style={{fontSize:22,fontWeight:800,letterSpacing:7}}>MEDIAGRID</span>
      <span style={{fontFamily:"ui-monospace, monospace",fontSize:18,letterSpacing:3,color:"#A0A8A0"}}>{String(index+1).padStart(2,"0")} / {String(total).padStart(2,"0")}</span>
    </div>
    <div style={{position:"absolute",top:284,left:86,right:86,display:"flex",alignItems:"center",gap:17,fontFamily:"ui-monospace, monospace",fontSize:20,letterSpacing:2.3,color:accent}}>
      <span style={{width:10,height:10,borderRadius:5,background:accent}}/>{reference||"PROPOSIÇÃO"}<span style={{flex:1,height:1,background:"#414C41"}}/>
    </div>
    <div style={{position:"absolute",top:500,left:86,right:86,opacity:enter,transform:`translateY(${(1-enter)*65}px)`}}>
      <div style={{fontFamily:"ui-monospace, monospace",fontSize:20,letterSpacing:4,color:"#DAC59B",marginBottom:33}}>{kicker}</div>
      <div style={{fontSize:text.length>62?69:text.length>35?79:94,fontWeight:750,letterSpacing:-3,lineHeight:1.06,overflowWrap:"break-word",maxWidth:890}}>{text}</div>
      <div style={{width:146,height:5,background:accent,marginTop:49}}/>
    </div>
    {scene.supporting_text&&<div style={{position:"absolute",top:980,left:86,right:110,borderLeft:`3px solid ${accent}`,paddingLeft:28,opacity:enter,transform:`translateY(${(1-enter)*30}px)`}}>
      <div style={{fontFamily:"ui-monospace, monospace",fontSize:17,letterSpacing:3,color:"#A0A8A0",marginBottom:18}}>NARRAÇÃO DESTA CENA</div>
      <div style={{fontSize:31,lineHeight:1.32,color:"#D8DDD5",maxWidth:800}}>{scene.supporting_text}</div>
    </div>}
    <div style={{position:"absolute",left:86,right:86,bottom:250,padding:"24px 0",borderTop:"1px solid #414C41",display:"flex",justifyContent:"space-between",gap:24,fontFamily:"ui-monospace, monospace",fontSize:18,letterSpacing:1.2,color:"#A0A8A0"}}>
      <span>PROPOSIÇÃO · CONFIRA A TRAMITAÇÃO ATUAL</span>
    </div>
    <div style={{position:"absolute",left:86,right:86,bottom:112,display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:20,color:"#A0A8A0"}}>
      <span>{sourceLabel||"Fonte oficial"}</span><span>{date?`CONSULTADO ${date}`:"CONSULTA REGISTRADA"}</span>
    </div>
    <div style={{position:"absolute",left:86,right:86,bottom:82,height:4,background:"#2A302B"}}><div style={{width:`${100*(index+progress)/total}%`,height:"100%",background:accent}}/></div>
  </AbsoluteFill>;
}

export function MediaGridVideo(input: Partial<RenderProps>) {
  const props = {...fallback, ...input};
  const {fps} = useVideoConfig();
  let start = 0;
  return <AbsoluteFill>{props.scenes.map((scene,index) => {
    const durationInFrames = Math.max(1, Math.round(scene.duration * fps));
    const item = <Sequence key={scene.scene_id} from={start} durationInFrames={durationInFrames}>{props.editorial_style==="official_politics"&&props.format==="vertical"?<OfficialPoliticsScene scene={scene} accent={props.accent} title={props.title} sourceLabel={props.source_label} reference={props.official_reference} checkedAt={props.source_checked_at} index={index} total={props.scenes.length}/>:<Scene scene={scene} accent={props.accent} title={props.title} sourceLabel={props.source_label}/>}</Sequence>;
    start += durationInFrames;
    return item;
  })}</AbsoluteFill>;
}
