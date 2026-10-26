"use client";

import {Player} from "@remotion/player";
import {useEffect, useState} from "react";
import {MediaGridTimelineV2} from "../../../renderer/src/timeline-v2";
import {api} from "../../lib/api";
import type {Asset, CreativeMotionPreview, CreativeReview, Job} from "../../lib/types";

export function CreativeMotionProof({projectId,revision,review,assets,dirty}:{
  projectId:string;revision:number;review:CreativeReview|null;assets:Asset[];dirty:boolean;
}) {
  const [soundtrack,setSoundtrack]=useState("");
  const [quality,setQuality]=useState<"preview"|"final">("preview");
  const [preview,setPreview]=useState<CreativeMotionPreview|null>(null);
  const [job,setJob]=useState<Job|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const approved=review?.status==="APPROVED_STORYBOARD"&&!review.blockers.length&&!dirty;
  const snapshot=review?.current_snapshot_sha256;
  useEffect(()=>{setPreview(null);setError("");},[snapshot,soundtrack,projectId,dirty]);
  useEffect(()=>{
    let active=true;
    void api.jobs().then((jobs)=>{if(active)setJob(jobs.find((j)=>j.project_id===projectId&&j.job_type==="CREATIVE_MOTION")??null);})
      .catch((e:unknown)=>{if(active)setError(String(e));});
    return()=>{active=false;};
  },[projectId]);
  useEffect(()=>{
    if(!job||!["QUEUED","RUNNING","WAITING_FOR_WORKER"].includes(job.status))return;
    let active=true;
    const timer=setInterval(()=>{void api.job(job.id).then((value)=>{if(active)setJob(value);})
      .catch((e:unknown)=>{if(active)setError(String(e));});},2000);
    return()=>{active=false;clearInterval(timer);};
  },[job?.id,job?.status]);
  const run=async(render:boolean)=>{
    if(!snapshot||!approved)return;
    setBusy(true);setError("");
    const request={expected_storyboard_revision:revision,expected_snapshot_sha256:snapshot,
      soundtrack_asset_id:soundtrack,quality};
    try {
      const current=await api.creativeMotionPreview(projectId,request);
      setPreview(current);
      if(render)setJob(await api.creativeMotionRender(projectId,request));
    }catch(e){setPreview(null);setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  };
  const props=preview?{...preview.props,sounds:preview.props.sounds?.map((sound)=>({
    ...sound,media_file:api.assetFile(sound.media_file),
  }))}:null;
  const currentOutput=approved&&job?.status==="SUCCEEDED"&&
    job.result?.approved_snapshot_sha256===snapshot;
  return <section className="creative-panel">
    <div className="creative-panel-head"><div><span>M3 / PROVA AUDIOVISUAL</span>
      <h3>Sports Motion</h3><p>12 segundos · quatro planos · áudio da biblioteca · revisão humana do vídeo pendente.</p></div>
      <span className="creative-status">{job?.status??"SEM RENDER"}</span></div>
    <p className="creative-help">Preset de esporte ficcional: planos de 2, 3, 4 e 3 segundos, 9:16 e 30 FPS.
      Usa Barlow Condensed e as três primeiras cores do DNA como fundo, texto e destaque.
      Os títulos aceitam duas linhas de até 16 caracteres. As descrições livres ficam registradas;
      este preset aplica quatro movimentos definidos.</p>
    {!approved&&<p className="creative-warning">Salve as alterações e aprove o storyboard atual para preparar a composição.</p>}
    <div className="creative-fields">
      <label>Trilha aprovada no brief e nos quatro planos<select value={soundtrack} onChange={(e)=>setSoundtrack(e.target.value)}>
        <option value="">Selecione o áudio</option>{assets.filter((a)=>a.media_type.startsWith("audio/")).map((a)=>
          <option key={a.id} value={a.id}>{a.name} · {a.rights_status}</option>)}</select></label>
      <label>Resolução do MP4<select value={quality} onChange={(e)=>setQuality(e.target.value as "preview"|"final")}>
        <option value="preview">Prévia · 540 × 960</option><option value="final">Final · 1080 × 1920</option></select></label>
    </div>
    <div className="creative-actions">
      <button type="button" disabled={!approved||!soundtrack||busy} onClick={()=>run(false)}>Preparar prévia com som</button>
      <button type="button" className="creative-primary" disabled={!approved||!soundtrack||busy} onClick={()=>run(true)}>
        {busy?"Verificando aprovação…":"Renderizar prova"}</button>
    </div>
    {error&&<p className="creative-warning" role="alert">{error}</p>}
    {props&&approved&&<><div style={{width:"min(100%, 360px)",aspectRatio:"9/16",margin:"24px auto"}}>
      <Player component={MediaGridTimelineV2} inputProps={props} compositionWidth={1080}
        compositionHeight={1920} durationInFrames={360} fps={30} controls
        style={{width:"100%",height:"100%"}} key={preview?.plan_sha256}/>
    </div><p className="creative-help">Plano derivado SHA-256: <code style={{overflowWrap:"anywhere"}}>{preview?.plan_sha256}</code></p></>}
    {job&&<p className="creative-help" role="status">Job {job.id} · {job.status}{job.error?` · ${job.error}`:""}</p>}
    {currentOutput&&<><video src={api.creativeMotionVideo(projectId,job.id)} controls preload="metadata"
      style={{display:"block",width:"min(100%, 360px)",margin:"24px auto"}}/>
      <p className="creative-help"><a href={api.creativeMotionVideo(projectId,job.id)} download>Baixar MP4 para avaliação humana</a>
        {" · "}SHA-256: <code style={{overflowWrap:"anywhere"}}>{String(job.result?.sha256)}</code></p></>}
  </section>;
}
