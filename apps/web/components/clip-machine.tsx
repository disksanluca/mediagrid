"use client";

import {useCallback, useEffect, useRef, useState} from "react";
import {api} from "@/lib/api";
import type {Asset, ClipCandidate} from "@/lib/types";

type JobState={id:string;status:string;error:string|null};
const describe:Record<string,string>={
  HIGH_SPEECH_COVERAGE:"Trecho com fala contínua",
  LOW_SPEECH_COVERAGE:"Inclui pausas",
  QUESTION:"Contém pergunta",
  SPEAKER_TURN:"Troca de falante marcada",
  START_NEEDS_REVIEW:"Confira o começo da frase",
  BOUNDARY_NEEDS_REVIEW:"Confira o fim da frase",
};
function stamp(ms:number){const seconds=Math.floor(ms/1000);return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,"0")}.${String(ms%1000).padStart(3,"0")}`;}
function message(reason:unknown){return reason instanceof Error?reason.message:String(reason);}

export function ClipMachine({asset,onClose,onRun}:{
  asset:Asset;onClose:()=>void;onRun:(action:()=>Promise<unknown>)=>Promise<void>;
}) {
  const video=useRef<HTMLVideoElement>(null);
  const [clips,setClips]=useState<ClipCandidate[]>([]);
  const [activeId,setActiveId]=useState<string|null>(null);
  const [start,setStart]=useState(0);
  const [end,setEnd]=useState(0);
  const [aspect,setAspect]=useState<"source"|"vertical">("source");
  const [focusX,setFocusX]=useState(.5);
  const [focusY,setFocusY]=useState(.5);
  const [analysis,setAnalysis]=useState<JobState|null>(null);
  const [render,setRender]=useState<JobState|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const active=clips.find((clip)=>clip.id===activeId)??null;
  const refresh=useCallback(async()=>{
    const current=await api.clips(asset.id);
    setClips(current);
    setError(null);
  },[asset.id]);
  useEffect(()=>{void refresh().catch((reason)=>setError(message(reason)));},[refresh]);
  useEffect(()=>{
    if(!activeId){setRender(null);return;}
    void api.clipRenderStatus(asset.id,activeId).then((job)=>setRender(job?{
      id:job.job_id,status:job.status,error:job.error,
    }:null)).catch((reason)=>setError(message(reason)));
  },[asset.id,activeId,active?.revision]);
  useEffect(()=>{
    if(!analysis||!["QUEUED","RUNNING"].includes(analysis.status))return;
    const timer=window.setInterval(()=>void api.job(analysis.id).then((job)=>{
      setAnalysis({id:job.id,status:job.status,error:job.error});
      if(job.status==="SUCCEEDED")void refresh();
    }).catch((reason)=>setError(message(reason))),3000);
    return ()=>window.clearInterval(timer);
  },[analysis,refresh]);
  useEffect(()=>{
    if(!render||!["QUEUED","RUNNING"].includes(render.status)||!activeId)return;
    const timer=window.setInterval(()=>void api.clipRenderStatus(asset.id,activeId).then((job)=>{
      if(job)setRender({id:job.job_id,status:job.status,error:job.error});
    }).catch((reason)=>setError(message(reason))),3000);
    return ()=>window.clearInterval(timer);
  },[asset.id,activeId,render]);
  const choose=(clip:ClipCandidate)=>{
    setActiveId(clip.id);setStart(clip.selected_start_ms??clip.start_ms);
    setEnd(clip.selected_end_ms??clip.end_ms);setAspect(clip.aspect);
    setFocusX(clip.focus_x);setFocusY(clip.focus_y);
    if(video.current)video.current.currentTime=clip.context_start_ms/1000;
  };
  const act=(action:()=>Promise<void>)=>void (async()=>{
    setBusy(true);setError(null);
    try{await action();}catch(reason){setError(message(reason));}finally{setBusy(false);}
  })();
  const analyze=()=>act(async()=>{await onRun(async()=>{
    const job=await api.analyzeClips(asset.id);
    setAnalysis({id:job.job_id,status:job.status,error:null});
    if(job.status==="SUCCEEDED")await refresh();
  });});
  const update=(action:"edit"|"select"|"reject")=>{
    if(!active)return;
    act(async()=>{
      const updated=await api.updateClip(asset.id,active.id,{
        expected_revision:active.revision,action,
        ...(action==="edit"?{start_ms:start,end_ms:end,aspect,focus_x:focusX,focus_y:focusY}:{}),
      });
      setClips((list)=>list.map((item)=>item.id===updated.id?updated:item));
      setRender(null);
    });
  };
  const startRender=()=>{
    if(!active)return;
    act(async()=>{await onRun(async()=>{
      const job=await api.renderClip(asset.id,active.id,active.revision);
      setRender({id:job.job_id,status:job.status,error:null});
    });});
  };
  const media=asset.metadata_json.proxy_sha256?api.assetProxy(asset.id):api.assetFile(asset.id);
  return <section className="panel clip-machine">
    <div className="panel-head"><div><h3>Máquina de cortes · {asset.name}</h3>
      <p>Candidatos baseados em palavras e pausas. Reveja o contexto antes de selecionar cada corte.</p></div>
      <button className="button small" onClick={onClose}>Fechar</button></div>
    <div className="panel-body">
      <div className="upload-actions"><button className="button primary" disabled={busy||!!analysis&&["QUEUED","RUNNING"].includes(analysis.status)} onClick={analyze}>Analisar fala</button>
        <button className="button small" disabled={busy} onClick={()=>void refresh().catch((reason)=>setError(message(reason)))}>Atualizar</button>
        {analysis&&<span className="small-note">Análise: {analysis.status}{analysis.error?` · ${analysis.error}`:""}</span>}</div>
      <p className="small-note">A pontuação só ordena janelas de fala. Ela não prevê alcance, emoção ou veracidade.</p>
      {error&&<p role="alert" className="alert">{error}</p>}
      <div className="clip-layout"><div className="clip-candidates">
        {clips.length?clips.map((clip)=><button key={clip.id} className={`clip-card ${clip.id===activeId?"selected":""}`} onClick={()=>choose(clip)}>
          <span>{stamp(clip.selected_start_ms??clip.start_ms)} → {stamp(clip.selected_end_ms??clip.end_ms)} · {clip.status}</span>
          <strong>{clip.spoken_text||"Sem texto neste intervalo"}</strong>
          <small>{clip.reason_codes.map((code)=>describe[code]??code).join(" · ")}</small>
        </button>):<p className="small-note">Analise uma mídia com transcrição temporizada aprovada para ver sugestões.</p>}
      </div><div className="clip-review">
        <video ref={video} controls preload="metadata" src={media} onTimeUpdate={(event)=>{
          if(active&&event.currentTarget.currentTime*1000>=active.context_end_ms)event.currentTarget.pause();
        }}/>
        {active?<><div className="upload-actions"><button className="button small" onClick={()=>{
          if(video.current){video.current.currentTime=active.context_start_ms/1000;void video.current.play();}
        }}>Ouvir contexto {stamp(active.context_start_ms)}–{stamp(active.context_end_ms)}</button>
          <span className="small-note">Fonte SHA {active.source_sha256.slice(0,12)} · revisão {active.transcript_revision}</span></div>
          {active.source_url&&<a href={active.source_url} target="_blank" rel="noreferrer">Abrir fonte original</a>}
          <div className="clip-context"><span>ANTES</span><p>{active.context_before||"Início da fonte"}</p>
            <span>CORTE</span><p>{active.spoken_text}</p><span>DEPOIS</span><p>{active.context_after||"Fim da fonte"}</p></div>
          <div className="clip-fields"><label>Entrada (ms)<input type="number" min="0" value={start} onChange={(event)=>setStart(Number(event.target.value))}/></label>
            <label>Saída (ms)<input type="number" min="1" value={end} onChange={(event)=>setEnd(Number(event.target.value))}/></label>
            <label>Formato<select value={aspect} onChange={(event)=>setAspect(event.target.value as "source"|"vertical")}><option value="source">Fonte</option><option value="vertical">9:16 manual</option></select></label>
            {aspect==="vertical"&&<><label>Foco X {focusX.toFixed(2)}<input type="range" min="0" max="1" step=".01" value={focusX} onChange={(event)=>setFocusX(Number(event.target.value))}/></label>
              <label>Foco Y {focusY.toFixed(2)}<input type="range" min="0" max="1" step=".01" value={focusY} onChange={(event)=>setFocusY(Number(event.target.value))}/></label></>}</div>
          <div className="upload-actions"><button className="button small" disabled={busy} onClick={()=>update("edit")}>Salvar limites e crop</button>
            <button className="button small" disabled={busy||active.status==="SELECTED"} onClick={()=>update("select")}>Selecionar corte</button>
            <button className="button small" disabled={busy||active.status==="REJECTED"} onClick={()=>update("reject")}>Rejeitar</button>
            <button className="button primary" disabled={busy||active.status!=="SELECTED"||!!render&&["QUEUED","RUNNING"].includes(render.status)} onClick={startRender}>Renderizar corte</button>
            {render?.status==="SUCCEEDED"&&<a className="button small" href={api.clipVideo(asset.id,active.id,render.id)}>Baixar MP4</a>}</div>
          {render&&<p className="small-note">Render: {render.status}{render.error?` · ${render.error}`:""}</p>}
        </>:<p className="small-note">Selecione um candidato para ver fonte, contexto e limites.</p>}
      </div></div>
    </div>
  </section>;
}
