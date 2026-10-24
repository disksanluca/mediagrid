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
    <div style={{fontSize: 74, lineHeight: 1.02, fontWeight: 900, maxWidth: 1300, whiteSpace: "pre-line", overflowWrap: "anywhere", ...motion}}>{scene.on_screen_text ?? title}</div>
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

function WikimediaTrendsScene({scene,accent,article,views,rank,observedOn,sourceLabel,index,total}:{scene:RenderScene;accent:string;article:string;views:number;rank:number;observedOn:string;sourceLabel?:string|null;index:number;total:number}) {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const enter=spring({frame,fps,config:{damping:20,stiffness:110}});
  const progress=Math.min(1,frame/Math.max(1,Math.round(scene.duration*fps)));
  const date=`${observedOn.slice(8,10)}/${observedOn.slice(5,7)}/${observedOn.slice(0,4)}`;
  const displayArticle=article.length>78?`${article.slice(0,77)}…`:article;
  const shownViews=Math.round(interpolate(frame,[0,Math.round(fps*1.1)],[0,views],{extrapolateRight:"clamp"})).toLocaleString("pt-BR");
  const isViews=scene.scene_id==="wiki-views";
  const isRank=scene.scene_id==="wiki-rank";
  return <AbsoluteFill style={{background:"radial-gradient(circle at 82% 44%, #254031 0%, #101812 60%, #0B0E0C 100%)",color:"#F1F3ED",fontFamily:"system-ui, sans-serif",overflow:"hidden"}}>
    <SceneMedia scene={scene} fps={fps}/>
    {scene.media_file&&<AbsoluteFill style={{background:"linear-gradient(90deg,rgba(11,14,12,.96),rgba(11,14,12,.63))"}}/>}
    <div style={{position:"absolute",left:86,right:86,top:106,display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:21,letterSpacing:6,fontWeight:800}}><span>MEDIAGRID</span><span style={{color:accent,fontFamily:"ui-monospace,monospace",letterSpacing:3}}>{String(index+1).padStart(2,"0")} / {String(total).padStart(2,"0")}</span></div>
    <div style={{position:"absolute",top:300,left:86,right:86,display:"flex",alignItems:"center",gap:18,color:accent,fontSize:21,letterSpacing:3,fontWeight:700}}><span style={{width:13,height:13,borderRadius:"50%",background:accent}}/>RADAR DE LEITURA<span style={{height:1,flex:1,background:"#516456"}}/></div>
    <div style={{position:"absolute",left:86,right:86,top:480,opacity:enter,transform:`translateY(${(1-enter)*65}px)`}}>
      {isViews?<>
        <div style={{fontSize:27,color:"#B8C2B8",marginBottom:28}}>ARTIGO NA WIKIPÉDIA EM PORTUGUÊS</div>
        <div style={{fontSize:displayArticle.length>48?68:82,fontWeight:800,lineHeight:1.04,letterSpacing:-2,overflowWrap:"anywhere",maxWidth:900}}>{displayArticle}</div>
        <div style={{marginTop:88,borderTop:`4px solid ${accent}`,paddingTop:37}}><div style={{fontSize:views>=1_000_000_000?80:views>=1_000_000?100:128,fontWeight:850,letterSpacing:-5,fontVariantNumeric:"tabular-nums",lineHeight:1}}>{shownViews}</div><div style={{fontSize:31,color:accent,marginTop:13}}>visualizações da página · {date}</div></div>
      </>:isRank?<>
        <div style={{fontSize:27,color:"#B8C2B8",marginBottom:25}}>POSIÇÃO NO RELATÓRIO DIÁRIO</div>
        <div style={{fontSize:245,fontWeight:850,letterSpacing:-10,lineHeight:.95,color:accent}}>#{rank}</div>
        <div style={{fontSize:58,fontWeight:750,lineHeight:1.09,marginTop:63,overflowWrap:"anywhere"}}>{displayArticle}</div>
        <div style={{fontSize:28,color:"#B8C2B8",marginTop:38}}>Páginas mais vistas · {date}</div>
      </>:<>
        <div style={{fontSize:27,color:accent,marginBottom:37}}>O QUE ESSE NÚMERO MEDE</div>
        <div style={{fontSize:74,fontWeight:800,lineHeight:1.08,letterSpacing:-2}}>Acessos à página da Wikipédia.</div>
        <div style={{marginTop:74,borderLeft:`5px solid ${accent}`,paddingLeft:29,fontSize:42,lineHeight:1.23,color:"#D4DDD2"}}>Não é audiência no Instagram<br/>nem interesse geral.</div>
      </>}
    </div>
    <div style={{position:"absolute",left:86,right:86,bottom:172,borderTop:"1px solid #516456",paddingTop:26,display:"flex",justifyContent:"space-between",alignItems:"center",gap:24,fontSize:21,color:"#B8C2B8"}}><span>{sourceLabel||"Fonte: Wikimedia Analytics"}</span><span>{date}</span></div>
    <div style={{position:"absolute",left:86,right:86,bottom:114,height:4,background:"#2D3B30"}}><div style={{width:`${100*(index+progress)/total}%`,height:"100%",background:accent}}/></div>
  </AbsoluteFill>;
}

function MusicbrainzScene({scene,accent,title,artist,firstDate,recordId,checkedAt,index,total}:{scene:RenderScene;accent:string;title:string;artist:string;firstDate:string;recordId:string;checkedAt?:string;index:number;total:number}) {
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const enter=spring({frame,fps,config:{damping:20,stiffness:120}});
  const progress=Math.min(1,frame/Math.max(1,Math.round(scene.duration*fps)));
  const identity=scene.scene_id==="music-identity";
  const dating=scene.scene_id==="music-date";
  const text=scene.on_screen_text||title;
  const date=checkedAt&&/^\d{4}-\d{2}-\d{2}$/.test(checkedAt)?`${checkedAt.slice(8,10)}/${checkedAt.slice(5,7)}/${checkedAt.slice(0,4)}`:"DATA DA CONSULTA INDISPONÍVEL";
  const vinylRotate=frame*0.12;
  return <AbsoluteFill style={{background:"radial-gradient(circle at 78% 20%, #314238 0%, #17211c 35%, #0B100D 75%)",color:"#F2F0E8",fontFamily:"system-ui, sans-serif",overflow:"hidden"}}>
    <SceneMedia scene={scene} fps={fps}/>
    {scene.media_file&&<AbsoluteFill style={{background:"linear-gradient(90deg,rgba(11,16,13,.97),rgba(11,16,13,.76))"}}/>}
    <div style={{position:"absolute",width:630,height:630,right:-225,top:300,borderRadius:"50%",border:"2px solid #576B57",boxShadow:"0 0 0 24px #151D18,0 0 0 27px #435146,0 0 0 65px #111A15,0 0 0 67px #334238,0 0 0 104px #101711,0 0 0 106px #2A3830",opacity:.65,transform:`rotate(${vinylRotate}deg)`}}><div style={{position:"absolute",inset:230,borderRadius:"50%",background:accent,boxShadow:"0 0 0 17px #253429"}}/><div style={{position:"absolute",width:17,height:17,borderRadius:"50%",background:"#0B100D",left:307,top:307}}/></div>
    <div style={{position:"absolute",top:103,left:86,right:86,display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:21,fontWeight:800,letterSpacing:6}}><span>MEDIAGRID</span><span style={{fontFamily:"ui-monospace, monospace",fontSize:18,color:accent,letterSpacing:2}}>{String(index+1).padStart(2,"0")} / {String(total).padStart(2,"0")}</span></div>
    <div style={{position:"absolute",top:275,left:86,right:86,display:"flex",alignItems:"center",gap:16,color:accent,fontSize:20,fontWeight:750,letterSpacing:4}}><span style={{width:11,height:11,borderRadius:"50%",background:accent}}/>FICHA MUSICAL<span style={{height:1,background:"#536859",flex:1}}/></div>
    <div style={{position:"absolute",left:86,right:86,top:470,opacity:enter,transform:`translateY(${(1-enter)*65}px)`}}>
      <div style={{fontFamily:"ui-monospace, monospace",fontSize:20,letterSpacing:3,color:"#ADC2A8",marginBottom:34}}>{identity?"IDENTIDADE DO REGISTRO":dating?"PRIMEIRA DATA CADASTRADA":"DIREITOS DE USO"}</div>
      {dating&&<div style={{fontSize:!firstDate?91:firstDate.length>4?143:235,lineHeight:.95,fontWeight:850,letterSpacing:-10,color:accent,marginBottom:43}}>{firstDate||"NÃO INFORMADA"}</div>}
      <div style={{fontSize:dating?56:text.length>75?56:text.length>42?70:84,fontWeight:790,lineHeight:1.08,letterSpacing:-2.5,maxWidth:900,overflowWrap:"anywhere"}}>{text}</div>
      {identity&&<div style={{marginTop:61,paddingTop:34,borderTop:`4px solid ${accent}`,fontSize:39,lineHeight:1.2,color:"#C8D8C5",overflowWrap:"anywhere"}}>Artista creditado · {artist}</div>}
      {!identity&&<div style={{marginTop:67,width:156,height:5,background:accent}}/>}
    </div>
    <div style={{position:"absolute",left:86,right:86,bottom:336,borderLeft:`3px solid ${accent}`,paddingLeft:25,fontSize:27,lineHeight:1.3,color:"#B9C7B8",maxWidth:835}}>{identity?"Crédito e título do grupo de lançamentos.":dating?"Campo do catálogo; confira a edição e a data antes de publicar.":"Este cartão não inclui gravação nem capa. Use mídia somente com direitos verificados."}</div>
    <div style={{position:"absolute",left:86,right:86,bottom:179,borderTop:"1px solid #536859",paddingTop:25,display:"flex",justifyContent:"space-between",gap:20,fontFamily:"ui-monospace, monospace",fontSize:17,color:"#ADBEAA"}}><span>FONTE · MUSICBRAINZ</span><span>CONSULTA {date}</span></div>
    <div style={{position:"absolute",left:86,right:86,bottom:127,fontFamily:"ui-monospace, monospace",fontSize:17,color:"#849784"}}>REGISTRO {recordId.slice(0,8).toUpperCase()} · METADADOS, NÃO LICENÇA DE ÁUDIO</div>
    <div style={{position:"absolute",left:86,right:86,bottom:91,height:4,background:"#304238"}}><div style={{width:`${100*(index+progress)/total}%`,height:"100%",background:accent}}/></div>
  </AbsoluteFill>;
}

export function MediaGridVideo(input: Partial<RenderProps>) {
  const props = {...fallback, ...input};
  const {fps} = useVideoConfig();
  let start = 0;
  return <AbsoluteFill>{props.scenes.map((scene,index) => {
    const durationInFrames = Math.max(1, Math.round(scene.duration * fps));
    const item = <Sequence key={scene.scene_id} from={start} durationInFrames={durationInFrames}>{props.editorial_style==="official_politics"&&props.format==="vertical"?<OfficialPoliticsScene scene={scene} accent={props.accent} title={props.title} sourceLabel={props.source_label} reference={props.official_reference} checkedAt={props.source_checked_at} index={index} total={props.scenes.length}/>:props.editorial_style==="wikimedia_trends"&&props.format==="vertical"&&props.wiki_article&&props.wiki_views&&props.wiki_rank&&props.wiki_observed_on?<WikimediaTrendsScene scene={scene} accent={props.accent} article={props.wiki_article} views={props.wiki_views} rank={props.wiki_rank} observedOn={props.wiki_observed_on} sourceLabel={props.source_label} index={index} total={props.scenes.length}/>:props.editorial_style==="musicbrainz_metadata"&&props.format==="vertical"&&props.music_title&&props.music_artist&&props.music_record_id?<MusicbrainzScene scene={scene} accent={props.accent} title={props.music_title} artist={props.music_artist} firstDate={props.music_first_release_date??""} recordId={props.music_record_id} checkedAt={props.source_checked_at} index={index} total={props.scenes.length}/>:<Scene scene={scene} accent={props.accent} title={props.title} sourceLabel={props.source_label}/>}</Sequence>;
    start += durationInFrames;
    return item;
  })}</AbsoluteFill>;
}
