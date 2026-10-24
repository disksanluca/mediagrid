"use client";

import {useEffect, useState} from "react";
import {api} from "@/lib/api";
import type {TimelineItem, TimelineResponse} from "@/lib/types";

type Cue={start_ms:number;end_ms:number;viseme:"closed"|"open"|"round"|"smile"};
type Props={projectId:string;timeline:TimelineResponse;selectedScene:string;busy:boolean;
  disabled:boolean;onRun:(action:()=>Promise<unknown>)=>Promise<void>;
  onSaved:(value:TimelineResponse)=>void};

export function CharacterDialogueEditor({projectId,timeline,selectedScene,busy,disabled,onRun,onSaved}:Props){
  const [draft,setDraft]=useState(timeline.edl);
  const [selectedId,setSelectedId]=useState<string|null>(null);
  useEffect(()=>setDraft(timeline.edl),[timeline]);
  const characters=draft.tracks.filter((track)=>track.kind==="caption").flatMap((track)=>
    track.items.filter((item)=>item.preset==="character_dialogue_v1"));
  const selected=characters.find((item)=>item.id===selectedId)??characters[0];
  const paired=Boolean(selected?.params.partner_character_id);
  const picture=draft.tracks.find((track)=>track.id==="picture")?.items.find(
    (item)=>item.params.scene_id===selectedScene);
  const changed=JSON.stringify(draft)!==JSON.stringify(timeline.edl);
  const update=(change:(item:TimelineItem)=>void)=>setDraft((current)=>{
    if(!selected)return current;
    const next=structuredClone(current);
    const item=next.tracks.flatMap((track)=>track.items).find((entry)=>entry.id===selected.id);
    if(item)change(item);
    return next;
  });
  const add=()=>{
    if(!picture||picture.duration_ms<1500)return;
    const duration=Math.min(6000,picture.duration_ms);
    const id=`character-${crypto.randomUUID()}`;
    setDraft((current)=>{
      const next=structuredClone(current);
      let track=next.tracks.find((entry)=>entry.id==="character-dialogue");
      if(!track){track={id:"character-dialogue",kind:"caption",items:[]};next.tracks.push(track);}
      track.items.push({id,start_ms:picture.start_ms,duration_ms:duration,
        z_index:18,source_asset_id:null,source_in_ms:null,source_out_ms:null,
        speed:1,preset:"character_dialogue_v1",params:{
          text:"Escreva a fala revisada aqui.",color:"#dcf769",character_id:"migo_v1",
          expression:"neutral",pose:"idle",
          mouth_cues:[{start_ms:0,end_ms:400,viseme:"closed"}],
          keyframes:[{at_ms:0,x:.5,y:.5,opacity:0,scale:.9},
            {at_ms:350,x:.5,y:.5,opacity:1,scale:1},
            {at_ms:duration,x:.5,y:.5,opacity:1,scale:1}],
        }});
      return next;
    });
    setSelectedId(id);
  };
  const cues=(selected?.params.mouth_cues??[]) as Cue[];
  const partnerCues=(selected?.params.partner_mouth_cues??[]) as Cue[];
  const changeCue=(index:number,patch:Partial<Cue>)=>update((item)=>{
    const revised=[...(item.params.mouth_cues as Cue[])];
    revised[index]={...revised[index],...patch};
    item.params.mouth_cues=revised;
  });
  const changePartnerCue=(index:number,patch:Partial<Cue>)=>update((item)=>{
    const revised=[...(item.params.partner_mouth_cues as Cue[])];
    revised[index]={...revised[index],...patch};
    item.params.partner_mouth_cues=revised;
  });
  const appendCue=()=>update((item)=>{
    const current=item.params.mouth_cues as Cue[];
    const start=current[current.length-1].end_ms;
    if(start+50>=item.duration_ms)return;
    item.params.mouth_cues=[...current,{start_ms:start,end_ms:Math.min(start+400,item.duration_ms),viseme:"open"}];
  });
  const appendPartnerCue=()=>update((item)=>{
    const current=item.params.partner_mouth_cues as Cue[];
    const start=current[current.length-1].end_ms;
    if(start+50>=item.duration_ms)return;
    item.params.partner_mouth_cues=[...current,{start_ms:start,end_ms:Math.min(start+400,item.duration_ms),viseme:"open"}];
  });
  const togglePartner=()=>update((item)=>{
    if(item.params.partner_character_id){
      for(const key of ["partner_character_id","partner_text","partner_color",
        "partner_expression","partner_pose","partner_mouth_cues"])delete item.params[key];
    }else{
      item.params.partner_character_id=item.params.character_id==="luma_v1"?"migo_v1":"luma_v1";
      item.params.partner_text="Escreva a resposta revisada.";
      item.params.partner_color=item.params.partner_character_id==="luma_v1"?"#80d5ed":"#dcf769";
      item.params.partner_expression="neutral";
      item.params.partner_pose="idle";
      item.params.partner_mouth_cues=[{start_ms:0,end_ms:400,viseme:"closed"}];
    }
  });
  const remove=()=>{
    if(!selected)return;
    setDraft((current)=>{
      const next=structuredClone(current);
      for(const track of next.tracks)track.items=track.items.filter((item)=>item.id!==selected.id);
      return next;
    });
    setSelectedId(null);
  };
  const validCues=cues.length>0&&cues.every((cue,index)=>cue.end_ms-cue.start_ms>=50&&
    cue.start_ms>=0&&cue.end_ms<=(selected?.duration_ms??0)&&
    (index===0||cue.start_ms>=cues[index-1].end_ms));
  const validPartnerCues=!paired||(partnerCues.length>0&&partnerCues.every((cue,index)=>
    cue.end_ms-cue.start_ms>=50&&cue.start_ms>=0&&cue.end_ms<=(selected?.duration_ms??0)&&
    (index===0||cue.start_ms>=partnerCues[index-1].end_ms)));
  const save=()=>void onRun(async()=>{
    await api.updateTimeline(projectId,{expected_revision:timeline.revision,
      expected_legacy_sha256:timeline.legacy_sha256,edl:draft});
    onSaved(await api.timeline(projectId));
  });
  return <section className="panel overlay-editor"><div className="panel-head"><div>
    <h3>Personagens 2D · Migo e Luma</h3><p>Rigs SVG originais, expressão, pose e boca marcada no tempo pela pessoa editora.</p>
  </div><button className="button small" disabled={busy||disabled||!picture||picture.duration_ms<1500}
    onClick={add}>Adicionar à cena</button></div><div className="panel-body">
    {characters.length?<div className="overlay-list">{characters.map((item)=><button key={item.id}
      className={`button small ${selected?.id===item.id?"selected":""}`}
      onClick={()=>setSelectedId(item.id)}>{item.params.partner_character_id?"Migo + Luma":item.params.character_id==="luma_v1"?"Luma":"Migo"} · {String(item.params.text??"Personagem").slice(0,45)}</button>)}</div>
      :<p className="small-note">Selecione uma cena de pelo menos 1,5 s para inserir o personagem.</p>}
    {selected&&<><div className="field-grid"><label className="field">Personagem<select
      value={String(selected.params.character_id??"migo_v1")}
      onChange={(event)=>update((item)=>{
        const previous=item.params.character_id;
        item.params.character_id=event.target.value;
        if(item.params.partner_character_id){
          item.params.partner_character_id=event.target.value==="luma_v1"?"migo_v1":"luma_v1";
          if(item.params.partner_color==="#80d5ed"||item.params.partner_color==="#dcf769")
            item.params.partner_color=item.params.partner_character_id==="luma_v1"?"#80d5ed":"#dcf769";
        }
        if(previous==="migo_v1"&&event.target.value==="luma_v1"&&item.params.color==="#dcf769")
          item.params.color="#80d5ed";
        if(previous==="luma_v1"&&event.target.value==="migo_v1"&&item.params.color==="#80d5ed")
          item.params.color="#dcf769";
      })}><option value="migo_v1">Migo</option><option value="luma_v1">Luma</option></select></label></div>
      <label className="field">Fala no balão<textarea rows={2} maxLength={paired?80:100}
      value={String(selected.params.text??"")} onChange={(event)=>update((item)=>{
        item.params.text=event.target.value;
      })}/></label><div className="field-grid">
      <label className="field">Expressão<select value={String(selected.params.expression??"neutral")}
        onChange={(event)=>update((item)=>{item.params.expression=event.target.value;})}>
        <option value="neutral">Neutra</option><option value="happy">Feliz</option>
        <option value="skeptical">Desconfiada</option><option value="surprised">Surpresa</option>
      </select></label><label className="field">Pose<select value={String(selected.params.pose??"idle")}
        onChange={(event)=>update((item)=>{item.params.pose=event.target.value;})}>
        <option value="idle">Parado</option><option value="point">Apontando</option>
        <option value="shrug">Ombros erguidos</option></select></label></div>
      <div className="field-grid"><label className="field">Cor do personagem<input type="color"
        value={String(selected.params.color??"#dcf769")}
        onChange={(event)=>update((item)=>{item.params.color=event.target.value;})}/></label>
        <label className="field">Início na timeline (s)<input type="number" min="0" step="0.1"
          value={selected.start_ms/1000} onChange={(event)=>update((item)=>{
            item.start_ms=Math.round(Number(event.target.value)*1000);
          })}/></label></div>
      <h4>Marcas manuais da boca</h4><p className="small-note">Tempos relativos ao início deste cartão. Ouça o WAV e ajuste cada marca; não há detecção de fonemas.</p>
      {cues.map((cue,index)=><div className="field-grid" key={index}>
        <label className="field">Início {index+1} (s)<input type="number" min="0" step="0.05"
          value={cue.start_ms/1000} onChange={(event)=>changeCue(index,{start_ms:Math.round(Number(event.target.value)*1000)})}/></label>
        <label className="field">Fim {index+1} (s)<input type="number" min="0.05" step="0.05"
          value={cue.end_ms/1000} onChange={(event)=>changeCue(index,{end_ms:Math.round(Number(event.target.value)*1000)})}/></label>
        <label className="field">Forma<select value={cue.viseme}
          onChange={(event)=>changeCue(index,{viseme:event.target.value as Cue["viseme"]})}>
          <option value="closed">Fechada</option><option value="open">Aberta</option>
          <option value="round">Arredondada</option><option value="smile">Sorriso</option>
        </select></label></div>)}
      <div className="upload-actions"><button className="button small" disabled={busy||disabled||cues.length>=64||
        !validCues||cues[cues.length-1]?.end_ms+50>selected.duration_ms}
        onClick={appendCue}>Adicionar marca</button>
        <button className="button small" disabled={busy||disabled||cues.length<=1}
          onClick={()=>update((item)=>{item.params.mouth_cues=(item.params.mouth_cues as Cue[]).slice(0,-1);})}>Remover última</button>
        <button className="button small" disabled={busy||disabled} onClick={remove}>Remover personagem</button></div>
      {!validCues&&<p className="small-note" role="alert">Marcas devem durar pelo menos 0,05 s, ficar ordenadas, sem sobreposição e dentro do cartão.</p>}
      <div className="upload-actions"><button className="button small"
        disabled={busy||disabled||(!paired&&String(selected.params.text??"").length>80)}
        onClick={togglePartner}>{paired?"Remover segundo personagem":"Mostrar Migo e Luma no mesmo quadro"}</button></div>
      {paired&&<><p className="small-note">Segundo rig: {selected.params.partner_character_id==="luma_v1"?"Luma":"Migo"}. Cada boca segue suas próprias marcas manuais; importe um WAV gravado com as duas vozes.</p>
        <label className="field">Fala do segundo personagem<textarea rows={2} maxLength={80}
          value={String(selected.params.partner_text??"")}
          onChange={(event)=>update((item)=>{item.params.partner_text=event.target.value;})}/></label>
        <div className="field-grid"><label className="field">Expressão do segundo<select
          value={String(selected.params.partner_expression??"neutral")}
          onChange={(event)=>update((item)=>{item.params.partner_expression=event.target.value;})}>
          <option value="neutral">Neutra</option><option value="happy">Feliz</option>
          <option value="skeptical">Desconfiada</option><option value="surprised">Surpresa</option>
        </select></label><label className="field">Pose do segundo<select
          value={String(selected.params.partner_pose??"idle")}
          onChange={(event)=>update((item)=>{item.params.partner_pose=event.target.value;})}>
          <option value="idle">Parado</option><option value="point">Apontando</option>
          <option value="shrug">Ombros erguidos</option></select></label>
        <label className="field">Cor do segundo<input type="color"
          value={String(selected.params.partner_color??"#80d5ed")}
          onChange={(event)=>update((item)=>{item.params.partner_color=event.target.value;})}/></label></div>
        <h4>Marcas manuais da boca · segundo personagem</h4>
        {partnerCues.map((cue,index)=><div className="field-grid" key={index}>
          <label className="field">Início {index+1} (s)<input type="number" min="0" step="0.05"
            value={cue.start_ms/1000} onChange={(event)=>changePartnerCue(index,{start_ms:Math.round(Number(event.target.value)*1000)})}/></label>
          <label className="field">Fim {index+1} (s)<input type="number" min="0.05" step="0.05"
            value={cue.end_ms/1000} onChange={(event)=>changePartnerCue(index,{end_ms:Math.round(Number(event.target.value)*1000)})}/></label>
          <label className="field">Forma<select value={cue.viseme}
            onChange={(event)=>changePartnerCue(index,{viseme:event.target.value as Cue["viseme"]})}>
            <option value="closed">Fechada</option><option value="open">Aberta</option>
            <option value="round">Arredondada</option><option value="smile">Sorriso</option>
          </select></label></div>)}
        <div className="upload-actions"><button className="button small"
          disabled={busy||disabled||partnerCues.length>=64||!validPartnerCues||
            partnerCues[partnerCues.length-1]?.end_ms+50>selected.duration_ms}
          onClick={appendPartnerCue}>Adicionar marca do segundo</button>
          <button className="button small" disabled={busy||disabled||partnerCues.length<=1}
            onClick={()=>update((item)=>{item.params.partner_mouth_cues=(item.params.partner_mouth_cues as Cue[]).slice(0,-1);})}>Remover última marca do segundo</button></div>
        {!validPartnerCues&&<p className="small-note" role="alert">As marcas do segundo personagem precisam ficar ordenadas e dentro do cartão.</p>}
      </>}
    </>}
    {changed&&<p className="small-note">Salve para atualizar a prévia e invalidar o MP4 anterior.</p>}
    <button className="button primary" disabled={busy||disabled||!changed||(characters.length>0&&(!validCues||!validPartnerCues))||
      characters.some((item)=>!String(item.params.text??"").trim()||
        (Boolean(item.params.partner_character_id)&&(!String(item.params.partner_text??"").trim()||
          String(item.params.text??"").length>80)))}
      onClick={save}>Salvar personagem na timeline</button>
    <p className="small-note">Você pode alternar cartões ou mostrar Migo e Luma juntos. As duas bocas seguem marcas manuais independentes. Para vozes diferentes, importe um WAV com as falas gravadas e revise o vídeo e áudio completos.</p>
  </div></section>;
}
