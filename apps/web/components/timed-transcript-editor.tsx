"use client";

import {useCallback, useEffect, useState} from "react";
import {api} from "@/lib/api";
import type {Asset, CaptionCue, TimedTranscript, TranscriptWord} from "@/lib/types";

function empty(assetId:string): TimedTranscript {
  return {asset_id:assetId,source_sha256:"",engine:"MANUAL",model_id:"human",
    model_version:"1",language:"pt",revision:0,status:"UNSAVED",words:[],cues:[]};
}

function message(reason:unknown):string {return reason instanceof Error?reason.message:String(reason);}

export function TimedTranscriptEditor({asset,onClose,onRun}:{
  asset:Asset;onClose:()=>void;onRun:(action:()=>Promise<unknown>)=>Promise<void>;
}) {
  const [saved,setSaved]=useState<TimedTranscript|null>(null);
  const [draft,setDraft]=useState<TimedTranscript>(empty(asset.id));
  const [asrAvailable,setAsrAvailable]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [jobId,setJobId]=useState<string|null>(null);
  const [captionJob,setCaptionJob]=useState<{id:string;status:string;error:string|null}|null>(null);
  const refresh=useCallback(async()=>{
    const [transcript,status,captionStatus]=await Promise.all([api.transcriptV2(asset.id),api.asrStatus(),api.captionRenderStatus(asset.id)]);
    setSaved(transcript);setDraft(transcript??empty(asset.id));
    setAsrAvailable(status.word_asr_available);setError(null);
    setCaptionJob(captionStatus?{id:captionStatus.job_id,status:captionStatus.status,error:captionStatus.error}:null);
  },[asset.id]);
  useEffect(()=>{void refresh().catch((reason)=>setError(message(reason)));},[refresh]);
  useEffect(()=>{
    if(!jobId&&(!captionJob||!["QUEUED","RUNNING"].includes(captionJob.status)))return;
    const timer=window.setInterval(()=>{
      if(jobId)void api.job(jobId).then((job)=>{
        if(job.status==="SUCCEEDED") {setJobId(null);void refresh();}
        else if(job.status==="FAILED") {setJobId(null);setError(job.error??"ASR falhou");}
      }).catch((reason)=>setError(message(reason)));
      if(captionJob&&["QUEUED","RUNNING"].includes(captionJob.status))
        void api.captionRenderStatus(asset.id).then((job)=>{
          if(job)setCaptionJob({id:job.job_id,status:job.status,error:job.error});
        }).catch((reason)=>setError(message(reason)));
    },3000);
    return ()=>window.clearInterval(timer);
  },[asset.id,captionJob,jobId,refresh]);
  const changed=JSON.stringify({language:draft.language,words:draft.words,cues:draft.cues})!==
    JSON.stringify({language:saved?.language??"pt",words:saved?.words??[],cues:saved?.cues??[]});
  const act=async(action:()=>Promise<void>)=>{
    setBusy(true);setError(null);
    try{await action();}catch(reason){setError(message(reason));}finally{setBusy(false);}
  };
  const updateWord=(index:number,field:keyof TranscriptWord,value:string|number)=>setDraft((current)=>{
    const words=current.words.map((word,i)=>i===index?{...word,[field]:value,edited:true}:word);
    return {...current,words};
  });
  const updateCue=(index:number,field:keyof CaptionCue,value:string|number)=>setDraft((current)=>{
    const cues=current.cues.map((cue,i)=>i===index?{...cue,[field]:value}:cue);
    return {...current,cues};
  });
  const save=()=>void act(async()=>{
    const result=await api.saveTranscript(asset.id,{expected_revision:draft.revision,
      language:draft.language,words:draft.words,cues:draft.cues});
    setSaved(result);setDraft(result);
  });
  const approve=()=>void act(async()=>{
    const result=await api.approveCaptions(asset.id,draft.revision);
    setSaved(result);setDraft(result);
  });
  const startAsr=()=>void act(async()=>{
    await onRun(async()=>{const result=await api.transcribeWords(asset.id);setJobId(result.job_id);});
  });
  const renderVideo=()=>void act(async()=>{
    await onRun(async()=>{
      const result=await api.renderCaptions(asset.id,draft.revision);
      setCaptionJob({id:result.job_id,status:result.status,error:null});
    });
  });
  const preview=asset.metadata_json.proxy_sha256?api.assetProxy(asset.id):api.assetFile(asset.id);
  return <section className="panel timed-transcript">
    <div className="panel-head"><div><h3>Palavras e legendas · {asset.name}</h3>
      <p>Confira texto e tempo ouvindo o arquivo inteiro. A aprovação libera SRT/VTT.</p></div>
      <button className="button small" onClick={onClose}>Fechar</button></div>
    <div className="panel-body">
      {asset.media_type.startsWith("video/")?<video controls preload="metadata" src={preview}/>:
        <audio controls preload="metadata" src={preview}/>}
      {asset.metadata_json.waveform_sha256&&<img className="timed-waveform" src={api.assetWaveform(asset.id)} alt="Forma de onda do áudio"/>}
      <div className="upload-actions"><button className="button small" disabled={busy||!asrAvailable||draft.revision>0}
        onClick={startAsr}>Transcrever com IA local</button>
        <button className="button small" disabled={busy} onClick={()=>void refresh().catch((reason)=>setError(message(reason)))}>Atualizar</button>
        <span className="small-note">{asrAvailable?"Modelo local disponível":"ASR por palavra indisponível; edição manual disponível"}
          {jobId?` · job ${jobId.slice(0,8)}`:""}</span></div>
      <div className="field-grid"><label className="field">Idioma<input value={draft.language}
        onChange={(event)=>setDraft({...draft,language:event.target.value})}/></label>
        <span className="small-note">Revisão {draft.revision} · {draft.status} · {draft.engine} {draft.model_version}</span></div>
      <details><summary>Palavras com tempo ({draft.words.length})</summary>
        <div className="timed-row timed-header"><span>Início (ms)</span><span>Fim (ms)</span><span>Palavra</span></div>
        <div className="timed-list">{draft.words.map((word,index)=><div className="timed-row" key={index}>
          <input aria-label={`Início da palavra ${index+1} em ms`} type="number" min="0" value={word.start_ms}
            onChange={(event)=>updateWord(index,"start_ms",Number(event.target.value))}/>
          <input aria-label={`Fim da palavra ${index+1} em ms`} type="number" min="1" value={word.end_ms}
            onChange={(event)=>updateWord(index,"end_ms",Number(event.target.value))}/>
          <input aria-label={`Palavra ${index+1}`} value={word.text}
            onChange={(event)=>updateWord(index,"text",event.target.value)}/>
          <button className="button small" onClick={()=>setDraft((current)=>({...current,
            words:current.words.filter((_,i)=>i!==index)}))}>Remover</button>
        </div>)}</div>
        <button className="button small" onClick={()=>setDraft((current)=>({...current,words:[...current.words,
          {start_ms:0,end_ms:500,text:"Nova palavra",confidence:null,speaker_id:null,edited:true}]}))}>Adicionar palavra</button>
      </details>
      <h4>Cues editáveis ({draft.cues.length})</h4>
      <div className="timed-row timed-header"><span>Início (ms)</span><span>Fim (ms)</span><span>Legenda</span></div>
      <div className="timed-list">{draft.cues.map((cue,index)=><div className="timed-row" key={index}>
        <input aria-label={`Início da legenda ${index+1} em ms`} type="number" min="0" value={cue.start_ms}
          onChange={(event)=>updateCue(index,"start_ms",Number(event.target.value))}/>
        <input aria-label={`Fim da legenda ${index+1} em ms`} type="number" min="1" value={cue.end_ms}
          onChange={(event)=>updateCue(index,"end_ms",Number(event.target.value))}/>
        <input aria-label={`Texto da legenda ${index+1}`} value={cue.text}
          onChange={(event)=>updateCue(index,"text",event.target.value)}/>
        <button className="button small" onClick={()=>setDraft((current)=>({...current,
          cues:current.cues.filter((_,i)=>i!==index)}))}>Remover</button>
      </div>)}</div>
      <div className="upload-actions"><button className="button small" onClick={()=>setDraft((current)=>({...current,
        cues:[...current.cues,{start_ms:0,end_ms:1000,text:"Nova legenda",speaker_id:null}]}))}>Adicionar legenda</button>
        <button className="button primary" disabled={busy||!changed} onClick={save}>Salvar correções</button>
        <button className="button small" disabled={busy||changed||draft.revision===0||!draft.cues.length||draft.status==="APPROVED"}
          onClick={approve}>Aprovar legendas</button>
        {draft.status==="APPROVED"&&<><a className="button small" href={api.captionFile(asset.id,"srt")}>Baixar SRT</a>
          <a className="button small" href={api.captionFile(asset.id,"vtt")}>Baixar VTT</a>
          {asset.media_type.startsWith("video/")&&<button className="button small" disabled={busy||!!captionJob&&["QUEUED","RUNNING"].includes(captionJob.status)}
            onClick={renderVideo}>Gerar MP4 legendado</button>}
          {captionJob?.status==="SUCCEEDED"&&<a className="button small" href={api.captionVideo(asset.id,captionJob.id)}>Baixar MP4</a>}
          {captionJob&&<span className="small-note">MP4: {captionJob.status}{captionJob.error?` · ${captionJob.error}`:""}</span>}</>}</div>
      {error&&<p className="small-note" role="alert">{error}</p>}
    </div>
  </section>;
}
