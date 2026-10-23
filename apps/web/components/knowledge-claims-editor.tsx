"use client";

import {useCallback, useEffect, useState} from "react";
import {api} from "@/lib/api";
import type {KnowledgeClaim, Scene} from "@/lib/types";

type Draft={scene_id:string;text:string;source_url:string;source_title:string;
  published_at:string;support_excerpt:string};
const empty:Draft={scene_id:"",text:"",source_url:"",source_title:"",
  published_at:"",support_excerpt:""};
function message(reason:unknown){return reason instanceof Error?reason.message:String(reason);}

export function KnowledgeClaimsEditor({projectId,scenes,onProjectRefresh}:{
  projectId:string;scenes:Scene[];onProjectRefresh:()=>Promise<void>;
}){
  const [claims,setClaims]=useState<KnowledgeClaim[]>([]);
  const [selectedId,setSelectedId]=useState<string|null>(null);
  const [draft,setDraft]=useState<Draft>(empty);
  const [sourceOpened,setSourceOpened]=useState(false);
  const [excerptChecked,setExcerptChecked]=useState(false);
  const [contextChecked,setContextChecked]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const selected=claims.find((claim)=>claim.id===selectedId)??null;
  const refresh=useCallback(async()=>setClaims(await api.claims(projectId)),[projectId]);
  useEffect(()=>{void refresh().catch((reason)=>setError(message(reason)));},[refresh]);
  useEffect(()=>{
    setDraft(selected?{scene_id:selected.scene_id,text:selected.text,
      source_url:selected.source_url,source_title:selected.source_title,
      published_at:selected.published_at,support_excerpt:selected.support_excerpt}
      :{...empty,scene_id:scenes[0]?.id??""});
    setSourceOpened(false);setExcerptChecked(false);setContextChecked(false);
  },[selectedId,selected?.revision,scenes]);
  const changed=selected?Object.keys(draft).some((key)=>
    draft[key as keyof Draft]!==selected[key as keyof Draft]):true;
  const valid=!!draft.scene_id&&draft.text.trim().length>=5&&
    /^https?:\/\//.test(draft.source_url)&&draft.source_title.trim().length>=3&&
    !!draft.published_at&&draft.support_excerpt.trim().length>=10;
  const act=(action:()=>Promise<void>)=>void(async()=>{
    setBusy(true);setError(null);
    try{await action();}catch(reason){setError(message(reason));}finally{setBusy(false);}
  })();
  const save=()=>act(async()=>{
    const result=selected?await api.saveClaim(projectId,selected.id,{
      ...draft,expected_revision:selected.revision,
    }):await api.addClaim(projectId,draft);
    await refresh();setSelectedId(result.id);await onProjectRefresh();
  });
  const approve=()=>act(async()=>{
    if(!selected)return;
    await api.approveClaim(projectId,selected.id,selected.revision);
    await refresh();setSourceOpened(false);setExcerptChecked(false);setContextChecked(false);
  });
  const remove=()=>act(async()=>{
    if(!selected)return;
    await api.removeClaim(projectId,selected.id,selected.revision);
    setSelectedId(null);await refresh();await onProjectRefresh();
  });
  return <section className="panel knowledge-claims"><div className="panel-head"><div>
    <h3>Alegações e fontes</h3><p>Vincule cada afirmação factual a uma cena e à evidência consultada.</p>
  </div><button className="button small" disabled={!scenes.length||busy} onClick={()=>setSelectedId(null)}>Nova alegação</button></div>
    <div className="panel-body">
      {!scenes.length&&<p className="small-note">Crie e salve o plano antes de vincular alegações às cenas.</p>}
      {claims.length>0&&<div className="overlay-list">{claims.map((claim)=><button key={claim.id}
        className={`button small ${selectedId===claim.id?"selected":""}`}
        onClick={()=>setSelectedId(claim.id)}>{claim.status==="APPROVED"?"✓ ":"Revisar · "}{claim.text.slice(0,55)}</button>)}</div>}
      <div className="field-grid"><label className="field">Cena<select value={draft.scene_id} onChange={(event)=>setDraft({...draft,scene_id:event.target.value})}>
        {scenes.map((scene,index)=><option key={scene.id} value={scene.id}>{index+1} · {scene.on_screen_text||scene.id}</option>)}</select></label>
        <label className="field">Publicada em<input type="date" value={draft.published_at} onChange={(event)=>setDraft({...draft,published_at:event.target.value})}/></label></div>
      <label className="field">Afirmação factual<textarea rows={2} maxLength={300} value={draft.text} onChange={(event)=>setDraft({...draft,text:event.target.value})} placeholder="Escreva uma alegação específica do vídeo"/></label>
      <div className="field-grid"><label className="field">Título da fonte<input maxLength={240} value={draft.source_title} onChange={(event)=>setDraft({...draft,source_title:event.target.value})}/></label>
        <label className="field">URL da fonte<input type="url" value={draft.source_url} onChange={(event)=>setDraft({...draft,source_url:event.target.value})} placeholder="https://..."/></label></div>
      <label className="field">Trecho que sustenta a alegação<textarea rows={3} maxLength={500} value={draft.support_excerpt} onChange={(event)=>setDraft({...draft,support_excerpt:event.target.value})} placeholder="Registre o trecho lido na fonte; não invente uma citação"/></label>
      {selected&&<p className="small-note">Revisão {selected.revision} · {selected.status} · {selected.reviewed_at?`conferida em ${new Date(selected.reviewed_at).toLocaleString("pt-BR")}`:"ainda sem conferência"}</p>}
      {error&&<p role="alert" className="alert">{error}</p>}
      <div className="upload-actions"><button className="button primary" disabled={busy||!scenes.length||!changed||!valid} onClick={save}>{selected?"Salvar nova revisão":"Adicionar alegação"}</button>
        {selected&&<button className="button small" disabled={busy} onClick={remove}>Remover do projeto</button>}</div>
      {selected&&selected.status==="REVIEW_REQUIRED"&&!changed&&<div className="review-checks">
        <a href={selected.source_url} target="_blank" rel="noopener noreferrer">Abrir fonte ↗</a>
        <label><input type="checkbox" checked={sourceOpened} onChange={(event)=>setSourceOpened(event.target.checked)}/> Abri a fonte original</label>
        <label><input type="checkbox" checked={excerptChecked} onChange={(event)=>setExcerptChecked(event.target.checked)}/> O trecho registrado confere</label>
        <label><input type="checkbox" checked={contextChecked} onChange={(event)=>setContextChecked(event.target.checked)}/> A alegação preserva o contexto e a data</label>
        <button className="button small" disabled={busy||!sourceOpened||!excerptChecked||!contextChecked} onClick={approve}>Aprovar esta alegação</button>
      </div>}
      <p className="small-note">O MediaGrid registra fonte, data e revisão; não verifica automaticamente a veracidade. A entrega manual de um projeto com alegações exige aprovação individual e URLs na revisão final.</p>
    </div></section>;
}
