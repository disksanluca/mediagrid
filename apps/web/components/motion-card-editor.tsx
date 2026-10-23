"use client";

import {useEffect, useState} from "react";
import {api} from "@/lib/api";
import type {TimelineItem, TimelineResponse} from "@/lib/types";

type Props={
  projectId:string;
  timeline:TimelineResponse;
  selectedScene:string;
  busy:boolean;
  disabled:boolean;
  onRun:(action:()=>Promise<unknown>)=>Promise<void>;
  onSaved:(value:TimelineResponse)=>void;
};

export function MotionCardEditor({projectId,timeline,selectedScene,busy,disabled,onRun,onSaved}:Props){
  const [draft,setDraft]=useState(timeline.edl);
  const [selectedId,setSelectedId]=useState<string|null>(null);
  useEffect(()=>setDraft(timeline.edl),[timeline]);
  const cards=draft.tracks.find((track)=>track.kind==="caption")?.items.filter(
    (item)=>item.preset==="motion_card_v1")??[];
  const selected=cards.find((item)=>item.id===selectedId)??cards[0];
  const changed=JSON.stringify(draft)!==JSON.stringify(timeline.edl);
  const picture=draft.tracks.find((track)=>track.id==="picture")?.items.find(
    (item)=>item.params.scene_id===selectedScene);
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
    if(!picture||picture.duration_ms<2500)return;
    const duration=Math.min(4000,picture.duration_ms);
    const id=`motion-card-${crypto.randomUUID()}`;
    setDraft((current)=>{
      const next=structuredClone(current);
      let track=next.tracks.find((entry)=>entry.kind==="caption");
      if(!track){track={id:"kinetic-titles",kind:"caption",items:[]};next.tracks.push(track);}
      track.items.push({id,start_ms:picture.start_ms,duration_ms:duration,z_index:15,
        source_asset_id:null,source_in_ms:null,source_out_ms:null,speed:1,
        preset:"motion_card_v1",params:{label:"IDEIA PRINCIPAL",text:"Título do cartão",
          body:"Escreva uma mensagem curta e verificável.",color:"#dcf769",layout:"stack",
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
  const save=()=>void onRun(async()=>{
    await api.updateTimeline(projectId,{expected_revision:timeline.revision,
      expected_legacy_sha256:timeline.legacy_sha256,edl:draft});
    onSaved(await api.timeline(projectId));
  });
  return <section className="panel overlay-editor">
    <div className="panel-head"><div><h3>Cartões em movimento</h3>
      <p>Mensagem, hierarquia e tempo editáveis na mesma timeline da prévia e do MP4.</p></div>
      <button className="button small" disabled={busy||disabled||!picture||picture.duration_ms<2500}
        onClick={add}>Adicionar cartão à cena</button></div>
    <div className="panel-body">
      {cards.length?<div className="overlay-list">{cards.map((item)=><button key={item.id}
        className={`button small ${selected?.id===item.id?"selected":""}`}
        onClick={()=>setSelectedId(item.id)}>{String(item.params.text??"Cartão")}</button>)}</div>
        :<p className="small-note">Selecione uma cena de pelo menos 2,5 s para criar um cartão.</p>}
      {selected&&<><div className="field-grid"><label className="field">Etiqueta<input maxLength={24}
        value={String(selected.params.label??"")} onChange={(event)=>update((item)=>{item.params.label=event.target.value;})}/></label>
        <label className="field">Título<input maxLength={60} value={String(selected.params.text??"")}
          onChange={(event)=>update((item)=>{item.params.text=event.target.value;})}/></label></div>
        <label className="field">Mensagem<textarea maxLength={100} rows={3} value={String(selected.params.body??"")}
          onChange={(event)=>update((item)=>{item.params.body=event.target.value;})}/></label>
        <div className="field-grid"><label className="field">Cor<input type="color" value={String(selected.params.color??"#dcf769")}
          onChange={(event)=>update((item)=>{item.params.color=event.target.value;})}/></label>
          <label className="field">Layout<select value={String(selected.params.layout??"stack")}
            onChange={(event)=>update((item)=>{item.params.layout=event.target.value;})}>
            <option value="stack">Empilhado</option><option value="split">Dividido no horizontal</option>
          </select></label></div>
        <div className="field-grid"><label className="field">Início (s)<input type="number" min="0" step="0.1"
          value={selected.start_ms/1000} onChange={(event)=>update((item)=>{item.start_ms=Math.round(Number(event.target.value)*1000);})}/></label>
          <label className="field">Duração (s)<input type="number" min="2.5" step="0.1"
            value={selected.duration_ms/1000} onChange={(event)=>update((item)=>{
              const duration=Math.round(Number(event.target.value)*1000);
              item.duration_ms=duration;
              const keyframes=item.params.keyframes as Array<{at_ms:number}>;
              keyframes[keyframes.length-1].at_ms=duration;
            })}/></label></div>
        <p className="small-note">O cartão permanece na área segura. Reveja o texto, suas fontes e o áudio no vídeo inteiro antes da exportação.</p>
        <button className="button small" disabled={busy||disabled} onClick={remove}>Remover cartão</button></>}
      {changed&&<p className="small-note">Salve a timeline para atualizar a prévia; a revisão invalida o render anterior.</p>}
      <button className="button primary" disabled={busy||disabled||!changed||cards.some((item)=>
        !String(item.params.label??"").trim()||!String(item.params.text??"").trim()||
        !String(item.params.body??"").trim())} onClick={save}>Salvar cartões na timeline</button>
    </div>
  </section>;
}
