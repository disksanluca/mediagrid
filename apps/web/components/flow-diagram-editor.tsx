"use client";

import {useEffect, useState} from "react";
import {api} from "@/lib/api";
import type {TimelineItem, TimelineResponse} from "@/lib/types";

type Props={projectId:string;timeline:TimelineResponse;selectedScene:string;busy:boolean;
  disabled:boolean;onRun:(action:()=>Promise<unknown>)=>Promise<void>;
  onSaved:(value:TimelineResponse)=>void};

export function FlowDiagramEditor({projectId,timeline,selectedScene,busy,disabled,onRun,onSaved}:Props){
  const [draft,setDraft]=useState(timeline.edl);
  const [selectedId,setSelectedId]=useState<string|null>(null);
  useEffect(()=>setDraft(timeline.edl),[timeline]);
  const diagrams=draft.tracks.filter((track)=>track.kind==="caption").flatMap((track)=>
    track.items.filter((item)=>item.preset==="flow_path_v1"));
  const selected=diagrams.find((item)=>item.id===selectedId)??diagrams[0];
  const picture=draft.tracks.find((track)=>track.id==="picture")?.items.find(
    (item)=>item.params.scene_id===selectedScene);
  const changed=JSON.stringify(draft)!==JSON.stringify(timeline.edl);
  const update=(change:(item:TimelineItem)=>void)=>{
    if(!selected)return;
    setDraft((current)=>{
      const next=structuredClone(current);
      const item=next.tracks.flatMap((track)=>track.items).find((entry)=>entry.id===selected.id);
      if(item)change(item);
      return next;
    });
  };
  const add=()=>{
    if(!picture||picture.duration_ms<3000)return;
    const duration=Math.min(5000,picture.duration_ms);
    const id=`flow-${crypto.randomUUID()}`;
    setDraft((current)=>{
      const next=structuredClone(current);
      let track=next.tracks.find((entry)=>entry.id==="flow-diagrams");
      if(!track){track={id:"flow-diagrams",kind:"caption",items:[]};next.tracks.push(track);}
      track.items.push({id,start_ms:picture.start_ms,duration_ms:duration,
        z_index:16,source_asset_id:null,source_in_ms:null,source_out_ms:null,
        speed:1,preset:"flow_path_v1",params:{text:"Como a ideia avança",
          steps:["Pesquisa", "Roteiro", "Vídeo"],color:"#dcf769",source_label:null,
          keyframes:[{at_ms:0,x:.5,y:.5,opacity:0,scale:.85},
            {at_ms:500,x:.5,y:.5,opacity:1,scale:1},
            {at_ms:duration,x:.5,y:.5,opacity:1,scale:1}]}});
      return next;
    });
    setSelectedId(id);
  };
  const remove=()=>{
    if(!selected)return;
    setDraft((current)=>{
      const next=structuredClone(current);
      for(const track of next.tracks)track.items=track.items.filter((item)=>item.id!==selected.id);
      return next;
    });
    setSelectedId(null);
  };
  const steps=(selected?.params.steps??[]) as string[];
  const save=()=>void onRun(async()=>{
    await api.updateTimeline(projectId,{expected_revision:timeline.revision,
      expected_legacy_sha256:timeline.legacy_sha256,edl:draft});
    onSaved(await api.timeline(projectId));
  });
  return <section className="panel overlay-editor">
    <div className="panel-head"><div><h3>Diagrama de ideias</h3>
      <p>Sequência visual de 2 a 4 etapas. Textos e tempo ficam no EDL do projeto.</p></div>
      <button className="button small" disabled={busy||disabled||!picture||picture.duration_ms<3000}
        onClick={add}>Adicionar à cena</button></div>
    <div className="panel-body">
      {diagrams.length?<div className="overlay-list">{diagrams.map((item)=><button key={item.id}
        className={`button small ${selected?.id===item.id?"selected":""}`}
        onClick={()=>setSelectedId(item.id)}>{String(item.params.text??"Diagrama")}</button>)}</div>
        :<p className="small-note">Selecione uma cena de pelo menos 3 s para criar um diagrama.</p>}
      {selected&&<><label className="field">Título<input maxLength={60}
        value={String(selected.params.text??"")} onChange={(event)=>update((item)=>{
          item.params.text=event.target.value;
        })}/></label>
        <div className="field-grid">{steps.map((step,index)=><label className="field" key={index}>
          Etapa {index+1}<input maxLength={32} value={step} onChange={(event)=>update((item)=>{
            const revised=[...(item.params.steps as string[])];revised[index]=event.target.value;
            item.params.steps=revised;
          })}/></label>)}</div>
        <div className="upload-actions"><button className="button small" disabled={busy||disabled||steps.length>=4}
          onClick={()=>update((item)=>{item.params.steps=[...(item.params.steps as string[]),"Nova etapa"];})}>Adicionar etapa</button>
          <button className="button small" disabled={busy||disabled||steps.length<=2}
            onClick={()=>update((item)=>{item.params.steps=(item.params.steps as string[]).slice(0,-1);})}>Remover última etapa</button></div>
        <div className="field-grid"><label className="field">Cor<input type="color"
          value={String(selected.params.color??"#dcf769")} onChange={(event)=>update((item)=>{
            item.params.color=event.target.value;
          })}/></label><label className="field">Crédito visível (opcional)<input maxLength={80}
          value={String(selected.params.source_label??"")} onChange={(event)=>update((item)=>{
            item.params.source_label=event.target.value||null;
          })}/></label></div>
        <div className="field-grid"><label className="field">Início (s)<input type="number" min="0" step="0.1"
          value={selected.start_ms/1000} onChange={(event)=>update((item)=>{
            item.start_ms=Math.round(Number(event.target.value)*1000);
          })}/></label><label className="field">Duração (s)<input type="number" min="3" step="0.1"
          value={selected.duration_ms/1000} onChange={(event)=>update((item)=>{
            const duration=Math.round(Number(event.target.value)*1000);
            item.duration_ms=duration;
            const keyframes=item.params.keyframes as Array<{at_ms:number}>;
            keyframes[keyframes.length-1].at_ms=duration;
          })}/></label></div>
        <p className="small-note">Um diagrama sem fonte é conceitual. Confira alegações e informe as URLs na revisão humana antes de entregar.</p>
        <button className="button small" disabled={busy||disabled} onClick={remove}>Remover diagrama</button></>}
      {changed&&<p className="small-note">Salve a revisão para atualizar a prévia e invalidar o MP4 anterior.</p>}
      <button className="button primary" disabled={busy||disabled||!changed||diagrams.some((item)=>
        !String(item.params.text??"").trim()||
        (item.params.steps as string[]).some((step)=>!step.trim()))}
        onClick={save}>Salvar diagramas na timeline</button>
    </div>
  </section>;
}
