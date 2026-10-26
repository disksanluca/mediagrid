"use client";

import {Player} from "@remotion/player";
import {useEffect,useRef,useState} from "react";
import {MediaGridTimelineV2} from "../../../renderer/src/timeline-v2";
import {api} from "../../lib/api";
import type {Asset,CreativeMotionPreview,CreativeReview,Job} from "../../lib/types";
import type {MotionArtifactReview,MotionEngineRequest,MotionRecipeInfo} from "../../lib/motion-types";

function ArtifactCard({job,projectId}:{job:Job;projectId:string}){
  const [review,setReview]=useState<MotionArtifactReview|null>(null);
  const [error,setError]=useState("");
  const [notes,setNotes]=useState("");
  const [confirmed,setConfirmed]=useState(false);
  const [busy,setBusy]=useState(false);
  useEffect(()=>{
    let active=true;
    void api.motionArtifactReview(projectId,job.id).then(value=>{if(active)setReview(value);})
      .catch(e=>{if(active)setError(String(e));});
    return()=>{active=false;};
  },[projectId,job.id,job.result?.sha256]);
  const decide=async(decision:"REQUEST_REVIEW"|"APPROVE"|"REJECT")=>{
    if(!review)return;setBusy(true);setError("");
    try{setReview(await api.motionArtifactDecision(projectId,job.id,{
      expected_revision:review.revision,expected_plan_sha256:review.plan_sha256,
      expected_video_sha256:review.video_sha256,decision,notes,
      video_watched:confirmed,audio_checked:confirmed,rights_checked:confirmed,
    }));setConfirmed(false);}
    catch(e){setError(String(e));}
    finally{setBusy(false);}
  };
  return <article className="creative-panel" style={{minWidth:0}}>
    <h4>Artefato {job.id.slice(0,8)}</h4>
    {error&&<p role="alert" className="creative-warning">{error}</p>}
    {review&&<>
      {!review.blockers.length&&<video src={api.creativeMotionVideo(projectId,job.id)} controls preload="metadata"
        style={{width:"100%",maxHeight:480,background:"#101a21"}}/>}
      {review.blockers.map(message=><p key={message} role="alert" className="creative-warning">{message}</p>)}
      <p className="creative-help">Revisão: {review.status} · r{review.revision}</p>
      <code style={{overflowWrap:"anywhere",fontSize:11}}>{review.video_sha256}</code>
      {!review.blockers.length&&<p><a href={api.creativeMotionVideo(projectId,job.id)} download>Baixar para avaliação</a></p>}
      <label>Notas da revisão<textarea value={notes} minLength={3} maxLength={2000}
        onChange={e=>setNotes(e.target.value)} style={{width:"100%"}}/></label>
      <label className="creative-check"><input type="checkbox" checked={confirmed}
        onChange={e=>setConfirmed(e.target.checked)}/> Assisti a este vídeo e conferi áudio e direitos.</label>
      <div className="creative-actions">
        <button disabled={busy||!!review.blockers.length||notes.trim().length<3} onClick={()=>decide("REQUEST_REVIEW")}>Solicitar revisão</button>
        <button disabled={busy||!!review.blockers.length||!confirmed||notes.trim().length<3} onClick={()=>decide("APPROVE")}>Aprovar este artefato</button>
        <button disabled={busy||!!review.blockers.length||notes.trim().length<3} onClick={()=>decide("REJECT")}>Rejeitar</button>
      </div>
      <p className="creative-help">A decisão vale para este hash. Publicação permanece desativada.</p>
      <details><summary>Histórico da revisão</summary>{review.history.map(r=><p key={r.revision}>
        r{r.revision} · {r.decision} · {r.actor}: {r.notes}</p>)}</details>
    </>}
  </article>;
}

export function CreativeMotionEngine({projectId,revision,review,assets,dirty}:{
  projectId:string;revision:number;review:CreativeReview|null;assets:Asset[];dirty:boolean;
}){
  const [recipes,setRecipes]=useState<MotionRecipeInfo[]>([]);
  const [selected,setSelected]=useState("");
  const [bindings,setBindings]=useState<Record<string,string>>({});
  const [textScale,setTextScale]=useState(1);
  const [gain,setGain]=useState(.8);
  const [diagnostics,setDiagnostics]=useState(false);
  const [quality,setQuality]=useState<"preview"|"final">("preview");
  const [preview,setPreview]=useState<CreativeMotionPreview|null>(null);
  const [jobs,setJobs]=useState<Job[]>([]);
  const [compare,setCompare]=useState<string[]>([]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const generation=useRef(0);
  const recipe=recipes.find(r=>r.id+"@"+r.version===selected);
  const approved=review?.status==="APPROVED_STORYBOARD"&&!review.blockers.length&&!dirty;
  const snapshot=review?.current_snapshot_sha256;
  const refresh=async()=>setJobs((await api.jobs()).filter(j=>j.project_id===projectId&&j.job_type==="CREATIVE_MOTION"));
  useEffect(()=>{
    let active=true;setJobs([]);setCompare([]);setPreview(null);
    void api.motionRecipes().then(v=>{if(active)setRecipes(v.recipes.filter(r=>r.status==="SUPPORTED"));}).catch(e=>{if(active)setError(String(e));});
    void api.jobs().then(v=>{if(active)setJobs(v.filter(j=>j.project_id===projectId&&j.job_type==="CREATIVE_MOTION"));}).catch(e=>{if(active)setError(String(e));});
    return()=>{active=false;};
  },[projectId]);
  useEffect(()=>{generation.current++;setPreview(null);},[projectId,snapshot,dirty,selected,bindings,textScale,gain,quality,diagnostics]);
  const pending=jobs.some(j=>["QUEUED","WAITING_FOR_WORKER","RUNNING"].includes(j.status));
  useEffect(()=>{
    if(!pending)return;
    const timer=setInterval(()=>{void refresh().catch(e=>setError(String(e)));},2000);
    return()=>clearInterval(timer);
  },[pending,projectId]);
  const ready=approved&&!!recipe&&Object.keys(recipe.asset_slots).every(slot=>!!bindings[slot]);
  const run=async(render:boolean)=>{
    if(!recipe||!snapshot||!ready)return;
    setBusy(true);setError("");
    const currentGeneration=generation.current;
    const request:MotionEngineRequest={
      expected_storyboard_revision:revision,expected_snapshot_sha256:snapshot,
      recipe:{id:recipe.id,version:recipe.version,sha256:recipe.sha256},asset_bindings:bindings,
      parameters:{text_scale:textScale,audio_gain:gain,diagnostics},quality,
    };
    try{
      const current=await api.motionEnginePreview(projectId,request);
      if(currentGeneration!==generation.current)return;
      setPreview(current);
      if(render){const job=await api.motionEngineRender(projectId,request);await refresh();setCompare([job.id]);}
    }catch(e){setPreview(null);setError(String(e));}
    finally{setBusy(false);}
  };
  const props=preview?{...preview.props,
    sounds:preview.props.sounds?.map(s=>({...s,media_file:api.assetFile(s.media_file)})),
    overlays:preview.props.overlays?.map(item=>item.preset==="motion_scene_v1"?{
      ...item,motion:{...item.motion,media_files:Object.fromEntries(Object.entries(
        item.motion.media_files).map(([slot,id])=>[slot,api.assetFile(id)]))},
    }:item),
  }:null;
  const config=preview?.plan.render;
  return <section className="creative-panel" aria-label="Motion Composition Engine">
    <div className="creative-panel-head"><div><span>MOTION ENGINE / V1</span>
      <h3>Direção audiovisual</h3><p>Receitas originais, prévia real e revisão do artefato exato.</p></div></div>
    {!approved&&<p className="creative-warning">Salve e aprove o storyboard vigente antes de preparar a composição.</p>}
    <div className="creative-fields">
      <label>Receita versionada<select value={selected} onChange={e=>{setSelected(e.target.value);setBindings({});}}>
        <option value="">Escolha uma receita</option>{recipes.map(r=><option key={r.id+r.version}
          value={r.id+"@"+r.version}>{r.id} · v{r.version}</option>)}</select></label>
      <label>Tamanho da tipografia<input type="range" min=".85" max="1.15" step=".05" value={textScale}
        onChange={e=>setTextScale(Number(e.target.value))}/>{Math.round(textScale*100)}%</label>
      <label>Ganho do áudio<input type="range" min=".1" max="1" step=".05" value={gain}
        onChange={e=>setGain(Number(e.target.value))}/>{Math.round(gain*100)}%</label>
      <label>Resolução do MP4<select value={quality} onChange={e=>setQuality(e.target.value as typeof quality)}>
        <option value="preview">Prévia · 50% da resolução</option><option value="final">Final · resolução integral</option></select></label>
      <label className="creative-check"><input type="checkbox" checked={diagnostics}
        onChange={e=>setDiagnostics(e.target.checked)}/> Mostrar diagnóstico e safe area</label>
      {recipe&&Object.entries(recipe.asset_slots).map(([slot,kind])=><label key={slot}>
        Asset {slot} · {kind}<select value={bindings[slot]??""}
          onChange={e=>setBindings({...bindings,[slot]:e.target.value})}>
          <option value="">Escolha mídia licenciada</option>
          {assets.filter(a=>a.media_type.startsWith(kind+"/")&&["OWNED","LICENSED"].includes(a.rights_status))
            .map(a=><option key={a.id} value={a.id}>{a.name} · {a.rights_status}</option>)}
        </select></label>)}
    </div>
    {recipe&&<p className="creative-help">{recipe.canvas.width} × {recipe.canvas.height} ·
      {recipe.shots.length} planos na ordem do storyboard · tempos de referência:
      {" "+recipe.shots.map(s=>s.reference_duration_ms/1000+" s").join(" / ")}.
      Durações vêm dos planos aprovados; os assets precisam constar no brief e nos planos que os usam.
      Fonte suportada no DNA: Barlow Condensed.</p>}
    <div className="creative-actions">
      <button disabled={!ready||busy} onClick={()=>run(false)}>Preparar prévia real</button>
      <button className="creative-primary" disabled={!ready||busy} onClick={()=>run(true)}>
        {busy?"Validando dependências…":"Renderizar MP4"}</button>
    </div>
    {error&&<p role="alert" className="creative-warning">{error}</p>}
    {props&&config&&approved&&<><div style={{maxWidth:720,maxHeight:640,margin:"24px auto",
      width:config.height>config.width?320:"100%",aspectRatio:config.width+"/"+config.height}}>
      <Player component={MediaGridTimelineV2} inputProps={props} controls
        compositionWidth={config.width} compositionHeight={config.height}
        durationInFrames={config.frames} fps={config.fps} key={preview.plan_sha256}
        style={{width:"100%",height:"100%"}}
        errorFallback={({error:playerError})=><p role="alert">Prévia bloqueada: {playerError.message}</p>}/>
    </div><p className="creative-help">Prévia técnica · aprovação audiovisual pendente.
      Plano <code style={{overflowWrap:"anywhere"}}>{preview.plan_sha256}</code></p></>}
    <h4>Renders e comparação</h4>
    {!jobs.length&&<p className="creative-help">Nenhum render neste projeto.</p>}
    {jobs.map(job=><div key={job.id} className="creative-source">
      <label><input type="checkbox" checked={compare.includes(job.id)}
        onChange={e=>setCompare(e.target.checked?[...compare.slice(-1),job.id]:compare.filter(id=>id!==job.id))}/>
        {job.id.slice(0,8)} · {job.status}</label>
      <span>{Math.round(job.progress*100)}%{job.error?" · "+job.error:""}</span>
      {["QUEUED","WAITING_FOR_WORKER"].includes(job.status)&&<button
        onClick={()=>void api.cancelJob(job.id).then(refresh).catch(e=>setError(String(e)))}>Cancelar espera</button>}
      {["FAILED","CANCELLED"].includes(job.status)&&<button
        onClick={()=>void api.retry(job.id).then(refresh).catch(e=>setError(String(e)))}>Tentar novamente</button>}
    </div>)}
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(280px,1fr))",gap:16}}>
      {jobs.filter(j=>compare.includes(j.id)&&j.status==="SUCCEEDED").map(job=>
        <ArtifactCard key={job.id+String(job.result?.sha256)} job={job} projectId={projectId}/>)}
    </div>
  </section>;
}
