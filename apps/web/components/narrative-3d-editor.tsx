"use client";

import {useCallback, useEffect, useState} from "react";
import {api} from "@/lib/api";
import type {Asset, Narrative3DSequence, Narrative3DShot} from "@/lib/types";

type State={job_id:string;status:string;progress:number;error:string|null};
type Quality="blocking"|"final";
const initialShots:Narrative3DShot[]=[
  {duration_ms:2500,beat_text:"Apresente o personagem e o ambiente.",action:"notice",camera:"wide",lighting:"calm"},
  {duration_ms:2500,beat_text:"Mostre a escolha ou a ação principal.",action:"reach",camera:"medium",lighting:"tense"},
  {duration_ms:2500,beat_text:"Mostre a consequência da ação.",action:"react",camera:"close",lighting:"bright"},
];
const actions:Record<Narrative3DShot["action"],string>={notice:"Perceber",reach:"Alcançar",react:"Reagir",celebrate:"Celebrar"};
const cameras:Record<Narrative3DShot["camera"],string>={wide:"Aberta",medium:"Média",close:"Próxima"};
const lights:Record<Narrative3DShot["lighting"],string>={calm:"Calma",tense:"Tensa",bright:"Clara"};
function message(error:unknown){return error instanceof Error?error.message:String(error);}

export function Narrative3DEditor({projectId,projectTitle,projectAspect,assets}:{projectId:string;
  projectTitle:string;projectAspect:string;assets:Asset[]}){
  const [saved,setSaved]=useState<Narrative3DSequence|null>(null);
  const [title,setTitle]=useState(projectTitle);
  const [aspect,setAspect]=useState<"vertical"|"horizontal">(projectAspect==="horizontal"?"horizontal":"vertical");
  const [shots,setShots]=useState<Narrative3DShot[]>(initialShots);
  const [audio,setAudio]=useState("");
  const [blocking,setBlocking]=useState<State|null>(null);
  const [final,setFinal]=useState<State|null>(null);
  const [watched,setWatched]=useState(false);
  const [continuity,setContinuity]=useState(false);
  const [timing,setTiming]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const availableAudio=assets.filter((item)=>item.media_type.startsWith("audio/")&&
    (item.rights_status==="OWNED"||item.rights_status==="LICENSED"&&!!item.license_name));
  const refresh=useCallback(async()=>{
    const [sequence,preview,output]=await Promise.all([api.narrative3d(projectId),
      api.narrative3dStatus(projectId,"blocking"),api.narrative3dStatus(projectId,"final")]);
    setSaved(sequence);setBlocking(preview);setFinal(output);
    if(sequence){setTitle(sequence.title);setAspect(sequence.aspect);setShots(sequence.shots);
      setAudio(sequence.audio_asset_id??"");}
  },[projectId]);
  useEffect(()=>{void refresh().catch((reason)=>setError(message(reason)));},[refresh]);
  useEffect(()=>{if(![blocking?.status,final?.status].some((value)=>
    value==="QUEUED"||value==="RUNNING"))return;
    const timer=window.setInterval(()=>void Promise.all([
      api.narrative3dStatus(projectId,"blocking"),api.narrative3dStatus(projectId,"final"),
    ]).then(([preview,output])=>{setBlocking(preview);setFinal(output);})
      .catch((reason)=>setError(message(reason))),3000);
    return()=>window.clearInterval(timer);
  },[projectId,blocking?.status,final?.status]);
  const changed=!saved||JSON.stringify({title,aspect,shots,audio})!==JSON.stringify({
    title:saved.title,aspect:saved.aspect,shots:saved.shots,audio:saved.audio_asset_id??"",
  });
  const act=(action:()=>Promise<void>)=>void(async()=>{
    setBusy(true);setError(null);
    try{await action();}catch(reason){setError(message(reason));}finally{setBusy(false);}
  })();
  const changeShot=(index:number,patch:Partial<Narrative3DShot>)=>setShots((current)=>
    current.map((shot,position)=>position===index?{...shot,...patch}:shot));
  const save=()=>act(async()=>{
    const sequence=await api.saveNarrative3d(projectId,{expected_revision:saved?.revision??0,
      title:title.trim(),aspect,shots,audio_asset_id:audio||null});
    setSaved(sequence);setShots(sequence.shots);setBlocking(null);setFinal(null);
    setWatched(false);setContinuity(false);setTiming(false);
  });
  const queue=(quality:Quality)=>act(async()=>{
    const job=await api.queueNarrative3d(projectId,quality);
    const next={...job,progress:0,error:null};
    if(quality==="blocking")setBlocking(next);else setFinal(next);
  });
  const approve=()=>act(async()=>{if(saved)setSaved(await api.approveNarrative3d(projectId,saved.revision));});
  const duration=shots.reduce((sum,shot)=>sum+shot.duration_ms,0)/1000;
  const active=[blocking?.status,final?.status].some((value)=>value==="QUEUED"||value==="RUNNING");
  return <section className="panel football-editor"><div className="panel-head"><div>
    <h3>Narrativa 3D · personagem original</h3>
    <p>Dirija três ou mais tomadas do mesmo rig/cenário. Blender local produz blocking e filme final.</p>
  </div><button className="button small" onClick={()=>void refresh().catch((reason)=>setError(message(reason)))}>Atualizar</button></div>
    <div className="panel-body"><p className="small-note">Migo 3D v1 e Atelier Stage v1 são geometria criada no MediaGrid. A estrutura inicial abaixo é editável; escreva os beats da sua história antes de renderizar. A trilha fica em silêncio se não houver áudio autorizado.</p>
      <div className="field-grid"><label className="field">Título da história<input minLength={3} maxLength={160} value={title} onChange={(event)=>setTitle(event.target.value)}/></label>
        <label className="field">Formato<select value={aspect} onChange={(event)=>setAspect(event.target.value as "vertical"|"horizontal")}>
          <option value="vertical">Vertical 9:16</option><option value="horizontal">Horizontal 16:9</option>
        </select></label></div>
      <label className="field">Trilha ou narração própria/licenciada (opcional)<select value={audio} onChange={(event)=>setAudio(event.target.value)}>
        <option value="">Sem áudio · silêncio identificado no MP4</option>
        {availableAudio.map((item)=><option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      {!availableAudio.length&&<p className="small-note">Importe um WAV/MP3 autorizado na Biblioteca para uma história com voz ou som.</p>}
      <div className="upload-actions"><button className="button small" disabled={busy||active||shots.length>=8}
        onClick={()=>setShots((current)=>[...current,{duration_ms:2500,beat_text:"Escreva um novo beat da história.",action:"react",camera:"medium",lighting:"calm"}])}>Adicionar tomada</button>
        <span className="small-note">{shots.length} tomadas · {duration.toFixed(1)} s · {saved?`revisão ${saved.revision} · ${saved.status}`:"sem revisão salva"}</span></div>
      {shots.map((shot,index)=><div className="scene-card" key={index}><div className="scene-head"><span>TOMADA {String(index+1).padStart(2,"0")}</span>
        <span><button className="scene-move" disabled={busy||active||index===0} aria-label={`Mover tomada ${index+1} para cima`} onClick={()=>setShots((current)=>{const next=[...current];[next[index-1],next[index]]=[next[index],next[index-1]];return next;})}>↑</button>
          <button className="scene-move" disabled={busy||active||index===shots.length-1} aria-label={`Mover tomada ${index+1} para baixo`} onClick={()=>setShots((current)=>{const next=[...current];[next[index+1],next[index]]=[next[index],next[index+1]];return next;})}>↓</button>
          <button className="scene-move" disabled={busy||active||shots.length<=3} aria-label={`Remover tomada ${index+1}`} onClick={()=>setShots((current)=>current.filter((_,position)=>position!==index))}>×</button></span></div>
        <label className="field">Beat / legenda na tela<input maxLength={180} value={shot.beat_text} onChange={(event)=>changeShot(index,{beat_text:event.target.value})}/></label>
        <div className="field-grid"><label className="field">Duração (s)<input type="number" min="1.5" max="6" step="0.1" value={shot.duration_ms/1000} onChange={(event)=>changeShot(index,{duration_ms:Math.round(Number(event.target.value)*1000)})}/></label>
          <label className="field">Ação<select value={shot.action} onChange={(event)=>changeShot(index,{action:event.target.value as Narrative3DShot["action"]})}>{Object.entries(actions).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
          <label className="field">Câmera<select value={shot.camera} onChange={(event)=>changeShot(index,{camera:event.target.value as Narrative3DShot["camera"]})}>{Object.entries(cameras).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
          <label className="field">Luz<select value={shot.lighting} onChange={(event)=>changeShot(index,{lighting:event.target.value as Narrative3DShot["lighting"]})}>{Object.entries(lights).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label></div>
      </div>)}
      {changed&&<p className="small-note">Salvar cria uma nova revisão e invalida blocking, aprovação e filme anteriores.</p>}
      <button className="button primary" disabled={busy||active||!changed||title.trim().length<3||shots.length<3||duration>45||shots.some((shot)=>shot.beat_text.trim().length<3||shot.duration_ms<1500||shot.duration_ms>6000)} onClick={save}>Salvar storyboard 3D</button>
      {saved?.status==="REVIEW_REQUIRED"&&!changed&&<div className="upload-actions"><button className="button small" disabled={busy||active} onClick={()=>queue("blocking")}>Renderizar blocking</button>
        <span className="small-note">Blender local: {saved.blender_available?"disponível":"ausente · job ficará WAITING_FOR_WORKER"}</span></div>}
      {blocking&&<p className="small-note">Blocking: {blocking.status} · {Math.round(blocking.progress*100)}%{blocking.error?` · ${blocking.error}`:""}</p>}
      {blocking?.status==="SUCCEEDED"&&saved?.status==="REVIEW_REQUIRED"&&!changed&&<><video className="editor-video" controls preload="metadata" src={api.narrative3dVideo(projectId,"blocking",blocking.job_id)} aria-label="Blocking 3D da revisão atual"/>
        <div className="review-checks"><label><input type="checkbox" checked={watched} onChange={(event)=>setWatched(event.target.checked)}/> Assisti ao blocking completo</label>
          <label><input type="checkbox" checked={continuity} onChange={(event)=>setContinuity(event.target.checked)}/> Conferi personagem e cenário nas tomadas</label>
          <label><input type="checkbox" checked={timing} onChange={(event)=>setTiming(event.target.checked)}/> Conferi ritmo, câmera e texto</label></div>
        <button className="button small" disabled={busy||!watched||!continuity||!timing} onClick={approve}>Aprovar blocking para render final</button></>}
      {saved?.status==="APPROVED"&&!changed&&<button className="button primary" disabled={busy||active} onClick={()=>queue("final")}>Renderizar filme 3D</button>}
      {final&&<p className="small-note">Filme: {final.status} · {Math.round(final.progress*100)}%{final.error?` · ${final.error}`:""}</p>}
      {final?.status==="SUCCEEDED"&&saved?.status==="APPROVED"&&!changed&&<><video className="editor-video" controls preload="metadata" src={api.narrative3dVideo(projectId,"final",final.job_id)} aria-label="Filme 3D da revisão atual"/>
        <a className="button small" href={api.narrative3dVideo(projectId,"final",final.job_id)} download>Baixar MP4 3D para revisão</a></>}
      {error&&<p role="alert" className="alert">{error}</p>}
      <p className="small-note">Este fluxo produz geometria original e não decide se a história está editorialmente pronta. Ouça e assista ao arquivo inteiro antes de qualquer entrega.</p>
    </div></section>;
}
