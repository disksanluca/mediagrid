"use client";

import {useCallback, useEffect, useState} from "react";
import {api} from "@/lib/api";
import type {CreativeDirections, Job} from "@/lib/types";

type AgentResult={task:string;content:unknown;content_sha256:string;model:string;
  model_digest:string;prompt_version:string;latency_ms:number;prompt_tokens:number;
  response_tokens:number;review_status:string;motion_readiness?:string;motion_blockers?:string[]};

const tasks:[string,string][]=[
  ["script","Roteiro POV"],["directions","Três direções"],
  ["storyboard","Storyboard"],["continuity","Continuidade"],
  ["references","Análise textual"],["motion","Planejar motion"],
  ["qa","Revisão técnica"],
];

export function CreativeLocalAgents({projectId,briefRevision,dnaRevision,directions,
  boardRevision,blocked,onChanged}:{projectId:string;briefRevision:number;dnaRevision:number;
  directions:CreativeDirections|null;boardRevision:number;blocked:boolean;
  onChanged:()=>Promise<void>}){
  const [status,setStatus]=useState<{state:string;model:string}|null>(null);
  const [jobs,setJobs]=useState<Job[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [directionId,setDirectionId]=useState("");
  const refresh=useCallback(async()=>{
    const [s,j]=await Promise.all([api.localAgentStatus(),api.localAgentJobs(projectId)]);
    setStatus(s);setJobs(j);
  },[projectId]);
  useEffect(()=>{
    void refresh().catch((reason)=>setError(String(reason)));
    const timer=setInterval(()=>void refresh().catch(()=>{}),5000);
    return()=>clearInterval(timer);
  },[refresh]);
  useEffect(()=>{
    if(directions?.content.directions.length&&!directionId)
      setDirectionId(directions.content.directions[0].id);
  },[directions,directionId]);
  const active=jobs.some((job)=>["QUEUED","RUNNING","WAITING_FOR_WORKER"].includes(job.status));
  async function start(task:string){
    setBusy(true);setError("");
    try{
      await api.startLocalAgent(projectId,task,briefRevision,dnaRevision,
        task==="storyboard"?directionId:undefined);
      await refresh();
    }catch(reason){setError(reason instanceof Error?reason.message:String(reason));}
    finally{setBusy(false);}
  }
  async function adopt(job:Job){
    setBusy(true);setError("");
    try{
      const base={expected_brief_revision:briefRevision,expected_dna_revision:dnaRevision,
        expected_revision:job.result&&job.result.task==="directions"?(directions?.revision??0):boardRevision,
        expected_direction_revision:directions?.revision??0};
      if(job.result?.task==="directions")await api.adoptLocalDirections(projectId,job.id,base);
      else await api.adoptLocalStoryboard(projectId,job.id,base);
      await onChanged();await refresh();
    }catch(reason){setError(reason instanceof Error?reason.message:String(reason));}
    finally{setBusy(false);}
  }
  return <details className="creative-local-agents">
    <summary>Assistentes criativos · Ollama local <strong>{status?.state??"VERIFICANDO"}</strong></summary>
    <div className="creative-local-body">
      <p>Rascunhos produzidos no PC. Modelo: {status?.model??"—"}. Nenhum agente aprova fatos, direitos ou publicação.</p>
      {error&&<p role="alert" className="creative-warning">{error}</p>}
      {(!briefRevision||!dnaRevision)&&<p>Salve o Brief e o DNA antes de gerar.</p>}
      {directions?.status==="CURRENT"&&<label>Direção para o storyboard <select value={directionId} onChange={(e)=>setDirectionId(e.target.value)}>{directions.content.directions.map((d)=><option key={d.id} value={d.id}>{d.title}</option>)}</select></label>}
      <div className="creative-local-buttons">{tasks.map(([id,label])=><button type="button" key={id}
        disabled={busy||blocked||active||status?.state!=="LOCAL"||!briefRevision||!dnaRevision||
          (["storyboard","motion","qa"].includes(id)&&directions?.status!=="CURRENT")}
        onClick={()=>void start(id)}>{label}</button>)}</div>
      {jobs.map((job)=>{
        const result=job.result as AgentResult|null;
        return <details key={job.id} className="creative-local-result">
          <summary><strong>{tasks.find(([id])=>id===(result?.task??job.job_type))?.[1]??job.job_type}</strong><span>{job.status} · {job.created_at}</span></summary>
          {job.error&&<p role="alert">{job.error}</p>}
          {result&&<><p>RASCUNHO · {result.model} · {result.prompt_version} · {result.latency_ms} ms · {result.prompt_tokens??"?"}/{result.response_tokens??"?"} tokens · hash {result.content_sha256?.slice(0,12)}</p>
            {result.motion_readiness&&<p>Compatibilidade M4: {result.motion_readiness}{result.motion_blockers?.length?` · ${result.motion_blockers.join("; ")}`:""}</p>}
            <pre>{JSON.stringify(result.content,null,2)}</pre>
            {["directions","storyboard"].includes(result.task)&&<button type="button" disabled={busy||blocked} onClick={()=>void adopt(job)}>Adotar no Creative Director para revisão</button>}
          </>}
        </details>;
      })}
    </div>
  </details>;
}
