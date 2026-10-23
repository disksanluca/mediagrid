"use client";

import {useCallback, useEffect, useState} from "react";
import {api} from "@/lib/api";
import type {Asset, FootballSequence, FootballShot} from "@/lib/types";

type RenderState={job_id:string;status:string;error:string|null};
const roles: Array<{value:FootballShot["role"];label:string}>=[
  {value:"build_up",label:"Preparação"}, {value:"action",label:"Ação"},
  {value:"reaction",label:"Reação"}, {value:"replay",label:"Replay"},
  {value:"celebration",label:"Celebração"},
];
function message(reason:unknown){return reason instanceof Error?reason.message:String(reason);}

export function FootballEditor({projectId,assets}:{projectId:string;assets:Asset[]}){
  const available=assets.filter((asset)=>asset.media_type.startsWith("video/")&&
    (asset.rights_status==="OWNED"||asset.rights_status==="LICENSED"&&!!asset.license_name));
  const [saved,setSaved]=useState<FootballSequence|null>(null);
  const [shots,setShots]=useState<FootballShot[]>([]);
  const [aspect,setAspect]=useState<"horizontal"|"vertical">("vertical");
  const [score,setScore]=useState("");
  const [scoreUrl,setScoreUrl]=useState("");
  const [eventsVerified,setEventsVerified]=useState(false);
  const [rightsVerified,setRightsVerified]=useState(false);
  const [scoreVerified,setScoreVerified]=useState(false);
  const [render,setRender]=useState<RenderState|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const refresh=useCallback(async()=>{
    const [sequence,job]=await Promise.all([api.football(projectId),api.footballRenderStatus(projectId)]);
    setSaved(sequence);setShots(sequence?.shots??[]);
    setAspect(sequence?.aspect??"vertical");setScore(sequence?.score_label??"");
    setScoreUrl(sequence?.score_source_url??"");setRender(job);
  },[projectId]);
  useEffect(()=>{void refresh().catch((reason)=>setError(message(reason)));},[refresh]);
  useEffect(()=>{if(!render||!["QUEUED","RUNNING"].includes(render.status))return;
    const timer=window.setInterval(()=>void api.footballRenderStatus(projectId).then(setRender)
      .catch((reason)=>setError(message(reason))),3000);
    return()=>window.clearInterval(timer);
  },[projectId,render]);
  const changed=JSON.stringify({shots,aspect,score,scoreUrl})!==JSON.stringify({
    shots:saved?.shots??[],aspect:saved?.aspect??"vertical",score:saved?.score_label??"",
    scoreUrl:saved?.score_source_url??"",
  });
  const act=(action:()=>Promise<void>)=>void(async()=>{
    setBusy(true);setError(null);
    try{await action();}catch(reason){setError(message(reason));}finally{setBusy(false);}
  })();
  const add=()=>{if(!available.length)return;setShots((current)=>[...current,{
    asset_id:available[0].id,in_ms:0,out_ms:3000,role:"build_up",
    verified_event_id:null,focus_x:.5,focus_y:.5,
  }]);};
  const change=(index:number,patch:Partial<FootballShot>)=>setShots((current)=>
    current.map((item,i)=>i===index?{...item,...patch}:item));
  const move=(index:number,direction:-1|1)=>setShots((current)=>{
    const target=index+direction;if(target<0||target>=current.length)return current;
    const next=[...current];[next[index],next[target]]=[next[target],next[index]];return next;
  });
  const save=()=>act(async()=>{
    const sequence=await api.saveFootball(projectId,{
      expected_revision:saved?.revision??0,aspect,shots,
      score_label:score.trim()||null,score_source_url:scoreUrl.trim()||null,
    });
    setSaved(sequence);setShots(sequence.shots);setRender(null);
    setEventsVerified(false);setRightsVerified(false);setScoreVerified(false);
  });
  const approve=()=>act(async()=>{
    if(!saved)return;
    setSaved(await api.approveFootball(projectId,saved.revision,scoreVerified));
  });
  const startRender=()=>act(async()=>{
    const job=await api.renderFootball(projectId);
    setRender({...job,error:null});
  });
  return <section className="panel football-editor"><div className="panel-head"><div>
    <h3>Football Edit · eventos manuais</h3>
    <p>Monte a sequência a partir de filmagem própria ou licenciada. O MediaGrid não detecta gols, jogadores nem placar automaticamente.</p>
  </div><button className="button small" onClick={()=>void refresh().catch((reason)=>setError(message(reason)))}>Atualizar</button></div>
    <div className="panel-body">
      {!available.length&&<p className="small-note">Importe um MP4 autorizado na Biblioteca e registre os direitos antes de criar os lances.</p>}
      <div className="field-grid"><label className="field">Formato<select value={aspect} onChange={(event)=>setAspect(event.target.value as "horizontal"|"vertical")}>
        <option value="vertical">9:16 com foco manual</option><option value="horizontal">16:9 com foco manual</option>
      </select></label><label className="field">Placar verificado (opcional)<input maxLength={80} value={score} onChange={(event)=>{setScore(event.target.value);if(!event.target.value)setScoreUrl("");}} placeholder="Time A 1 × 0 Time B"/></label></div>
      {(score||scoreUrl)&&<label className="field">URL da fonte do placar<input type="url" value={scoreUrl} onChange={(event)=>setScoreUrl(event.target.value)} placeholder="https://..."/></label>}
      <div className="upload-actions"><button className="button small" disabled={!available.length||busy||shots.length>=24} onClick={add}>Adicionar lance</button>
        <span className="small-note">{shots.length} lances · {saved?`revisão ${saved.revision} · ${saved.status}`:"ainda não salvo"}</span></div>
      {shots.map((shot,index)=>{const asset=assets.find((item)=>item.id===shot.asset_id);
        return <div className="scene-card" key={index}><div className="scene-head"><span>{String(index+1).padStart(2,"0")} · {roles.find((role)=>role.value===shot.role)?.label}</span>
          <span><button className="scene-move" disabled={index===0} aria-label={`Mover lance ${index+1} para cima`} onClick={()=>move(index,-1)}>↑</button>
            <button className="scene-move" disabled={index===shots.length-1} aria-label={`Mover lance ${index+1} para baixo`} onClick={()=>move(index,1)}>↓</button>
            <button className="scene-move" aria-label={`Remover lance ${index+1}`} onClick={()=>setShots((current)=>current.filter((_,i)=>i!==index))}>×</button></span></div>
          <div className="field-grid"><label className="field">Filmagem<select value={shot.asset_id} onChange={(event)=>change(index,{asset_id:event.target.value})}>
            {available.map((item)=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label className="field">Função no arco<select value={shot.role} onChange={(event)=>change(index,{role:event.target.value as FootballShot["role"]})}>
              {roles.map((role)=><option key={role.value} value={role.value}>{role.label}</option>)}</select></label></div>
          {asset&&<video controls preload="metadata" src={asset.metadata_json.proxy_sha256?api.assetProxy(asset.id):api.assetFile(asset.id)} aria-label={`Revisar origem do lance ${index+1}`}/>}
          <div className="field-grid"><label className="field">Entrada (ms)<input type="number" min="0" value={shot.in_ms} onChange={(event)=>change(index,{in_ms:Number(event.target.value)})}/></label>
            <label className="field">Saída (ms)<input type="number" min="1" value={shot.out_ms} onChange={(event)=>change(index,{out_ms:Number(event.target.value)})}/></label>
            <label className="field">ID do evento conferido<input value={shot.verified_event_id??""} maxLength={80} onChange={(event)=>change(index,{verified_event_id:event.target.value||null})} placeholder="Ex.: lance-01"/></label></div>
          <div className="field-grid"><label className="field">Foco X {shot.focus_x.toFixed(2)}<input type="range" min="0" max="1" step=".01" value={shot.focus_x} onChange={(event)=>change(index,{focus_x:Number(event.target.value)})}/></label>
            <label className="field">Foco Y {shot.focus_y.toFixed(2)}<input type="range" min="0" max="1" step=".01" value={shot.focus_y} onChange={(event)=>change(index,{focus_y:Number(event.target.value)})}/></label></div>
          {shot.source_sha256&&<p className="small-note">Origem SHA-256 {shot.source_sha256.slice(0,16)}…</p>}
        </div>;})}
      {error&&<p role="alert" className="alert">{error}</p>}
      {changed&&<p className="small-note">Alterações exigem salvar e nova aprovação. O MP4 da revisão anterior deixa de ser entregue.</p>}
      <button className="button primary" disabled={busy||!changed||!shots.length} onClick={save}>Salvar sequência</button>
      {saved&&<div className="review-checks"><label><input type="checkbox" checked={eventsVerified} onChange={(event)=>setEventsVerified(event.target.checked)}/> Conferi cada evento e o replay na filmagem original</label>
        <label><input type="checkbox" checked={rightsVerified} onChange={(event)=>setRightsVerified(event.target.checked)}/> Conferi direitos da filmagem</label>
        {score&&<label><input type="checkbox" checked={scoreVerified} onChange={(event)=>setScoreVerified(event.target.checked)}/> Conferi placar e fonte</label>}</div>}
      {saved?.status==="REVIEW_REQUIRED"&&<button className="button small" disabled={busy||changed||!eventsVerified||!rightsVerified||!!score&&!scoreVerified} onClick={approve}>Aprovar montagem para render</button>}
      {saved?.status==="APPROVED"&&<button className="button primary" disabled={busy||changed||!!render&&["QUEUED","RUNNING"].includes(render.status)} onClick={startRender}>Renderizar Football Edit</button>}
      {render&&<p className="small-note">Worker: {render.status}{render.error?` · ${render.error}`:""}</p>}
      {render?.status==="SUCCEEDED"&&saved?.status==="APPROVED"&&!changed&&<a className="button small" href={api.footballVideo(projectId,render.job_id)} download>Baixar MP4 para revisão</a>}
      <p className="small-note">Ouça e assista ao MP4 inteiro. Placar e replay são rótulos inseridos a partir da revisão humana; não há detecção automática.</p>
    </div></section>;
}
