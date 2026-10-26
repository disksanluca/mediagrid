"use client";

import {useCallback, useEffect, useState} from "react";
import {AlertTriangle, ArrowDown, ArrowUp, Check, Plus, RefreshCw, Save, Trash2} from "lucide-react";
import {ApiError, api} from "@/lib/api";
import type {Asset, Channel, CreativeBrief, CreativeDNA, CreativeDirections, CreativeReview, CreativeRevision, CreativeStoryboard, CreativeStoryboardRevision, KnowledgeClaim, Project, StoryboardShot} from "@/lib/types";
import {blankShot,moveShot,removeShot,resizeShot,sequence,splitShot,syncDuration} from "./storyboard-draft";
import "./creative-workspace.css";
import {CreativeMotionProof} from "./creative-motion-proof";

type Step="brief"|"dna"|"directions"|"storyboard"|"review";
const steps: {id:Step;label:string}[]=[{id:"brief",label:"Brief"},{id:"dna",label:"DNA"},{id:"directions",label:"Direções"},{id:"storyboard",label:"Storyboard"},{id:"review",label:"Revisão"}];
const list=(value:string)=>value.split(/\r?\n/).map((line)=>line.trim()).filter(Boolean);
const lines=(values:string[])=>values.join("\n");
const issue=(reason:unknown)=>reason instanceof Error?reason.message:"Não foi possível concluir a operação.";
const isAbsent=(reason:unknown)=>reason instanceof ApiError&&reason.status===404;
const ms=(value:number)=>`${(value/1000).toFixed(1)} s`;

function initialBrief(project:Project):CreativeBrief {
  const total=project.plan?.scenes?.reduce((sum,scene)=>sum+scene.duration_seconds*1000,0)??30000;
  const duration=Math.max(3000,Math.min(600000,Math.round(total)));
  return {schema_version:"brief_v1",topic:project.topic,audience:"",objective:"",format:project.format as CreativeBrief["format"],duration_ms:duration,fps:30,language:"pt-BR",factual_mode:"FACT_CHECK_REQUIRED",sources:[],asset_ids:[],restrictions:[],style_notes:""};
}
const emptyDNA:CreativeDNA={schema_version:"creative_dna_v1",palette:["#D0E5BC","#151A17"],font_display:"Space Grotesk",font_body:"DM Sans",tone:"",energy:"balanced",must_have:[],avoid:[],max_words_per_card:10};

async function optional<T>(call:()=>Promise<T>):Promise<T|null>{try{return await call();}catch(reason){if(isAbsent(reason))return null;throw reason;}}

export function CreativeWorkspace({project,channel,assets}:{project:Project;channel:Channel;assets:Asset[]}) {
  const [step,setStep]=useState<Step>("brief");
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState<string|null>(null);
  const [notice,setNotice]=useState("");
  const [error,setError]=useState("");
  const [conflict,setConflict]=useState(false);
  const [conflictLoaded,setConflictLoaded]=useState(false);
  const [briefRow,setBriefRow]=useState<CreativeRevision<CreativeBrief>|null>(null);
  const [dnaRow,setDnaRow]=useState<CreativeRevision<CreativeDNA>|null>(null);
  const [directions,setDirections]=useState<CreativeDirections|null>(null);
  const [boardRow,setBoardRow]=useState<CreativeStoryboardRevision|null>(null);
  const [review,setReview]=useState<CreativeReview|null>(null);
  const [brief,setBrief]=useState<CreativeBrief>(()=>initialBrief(project));
  const [dna,setDna]=useState<CreativeDNA>(emptyDNA);
  const [restrictionsText,setRestrictionsText]=useState("");
  const [mustHaveText,setMustHaveText]=useState("");
  const [avoidText,setAvoidText]=useState("");
  const [board,setBoard]=useState<CreativeStoryboard|null>(null);
  const [claims,setClaims]=useState<KnowledgeClaim[]>([]);
  const [actor,setActor]=useState("");
  const [notes,setNotes]=useState("");
  const [checks,setChecks]=useState({storyboard:false,rights:false,facts:false});

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    try {
      const [b,d,ds,s,r,c]=await Promise.all([
        optional(()=>api.creativeBrief(project.id)),optional(()=>api.creativeDNA(channel.id)),
        optional(()=>api.creativeDirections(project.id)),optional(()=>api.creativeStoryboard(project.id)),
        optional(()=>api.creativeReview(project.id)),api.claims(project.id),
      ]);
      setBriefRow(b);setDnaRow(d);setDirections(ds);setBoardRow(s);setReview(r);setClaims(c);
      setBrief(b?.content??initialBrief(project));setDna(d?.content??emptyDNA);setBoard(s?.content??null);
      setRestrictionsText(lines(b?.content.restrictions??[]));setMustHaveText(lines(d?.content.must_have??[]));setAvoidText(lines(d?.content.avoid??[]));
      setConflict(false);setConflictLoaded(false);setNotice("");
    }catch(reason){setError(issue(reason));}finally{setLoading(false);}
  },[project.id,channel.id]);
  useEffect(()=>{void load();},[load]);

  const run=async(key:string,action:()=>Promise<void>,successMessage="Alteração salva. Consulte o estado atualizado abaixo.")=>{
    setBusy(key);setError("");setNotice("");
    try{await action();setNotice(successMessage);}
    catch(reason){setError(issue(reason));if(reason instanceof ApiError&&reason.status===409){setConflict(true);setConflictLoaded(false);}}
    finally{setBusy(null);}
  };
  const refreshDerived=async()=>{
    const [ds,s,r]=await Promise.all([optional(()=>api.creativeDirections(project.id)),optional(()=>api.creativeStoryboard(project.id)),optional(()=>api.creativeReview(project.id))]);
    setDirections(ds);setBoardRow(s);setReview(r);
  };
  const refreshRevision=async()=>{
    setBusy("reload");setError("");
    try{
      const [b,d,ds,s,r,c]=await Promise.all([
        optional(()=>api.creativeBrief(project.id)),optional(()=>api.creativeDNA(channel.id)),
        optional(()=>api.creativeDirections(project.id)),optional(()=>api.creativeStoryboard(project.id)),optional(()=>api.creativeReview(project.id)),api.claims(project.id),
      ]);
      setBriefRow(b);setDnaRow(d);setDirections(ds);setBoardRow(s);setReview(r);setClaims(c);
      const changed=(b?.revision??0)!==(briefRow?.revision??0)||(d?.revision??0)!==(dnaRow?.revision??0)||(s?.revision??0)!==(boardRow?.revision??0)||(ds?.revision??0)!==(directions?.revision??0);
      setConflict(conflict||changed);setConflictLoaded(conflict||changed);
      setNotice("Revisões do servidor atualizadas. Seu rascunho local foi preservado.");
    }catch(reason){setError(issue(reason));}finally{setBusy(null);}
  };
  const saveBrief=()=>void run("brief",async()=>{
    if(brief.topic.trim().length<3||brief.audience.trim().length<2||brief.objective.trim().length<5)throw new Error("Preencha tópico, audiência e objetivo com o detalhe mínimo exigido.");
    const saved=await api.saveCreativeBrief(project.id,briefRow?.revision??0,brief);
    setBriefRow(saved);setBrief(saved.content);await refreshDerived();
  });
  const saveDNA=()=>void run("dna",async()=>{
    const saved=await api.saveCreativeDNA(channel.id,dnaRow?.revision??0,dna);
    setDnaRow(saved);setDna(saved.content);await refreshDerived();
  });
  const generate=()=>void run("directions",async()=>{
    if(!briefRow||!dnaRow)throw new Error("Salve o brief e o DNA antes de gerar direções.");
    const saved=await api.generateCreativeDirections(project.id,directions?.revision??0,briefRow.revision,dnaRow.revision);
    setDirections(saved);setReview(await optional(()=>api.creativeReview(project.id)));
  },"Propostas carregadas da API. Confira a revisão e a origem antes de selecionar.");
  const chooseDirection=(id:string)=>{
    if(!briefRow)return;
    setBoard((current)=>current?{...current,direction_id:id}:{schema_version:"storyboard_v1",direction_id:id,duration_ms:briefRow.content.duration_ms,fps:briefRow.content.fps,shots:[blankShot(briefRow.content.duration_ms)]});
    setStep("storyboard");setNotice("Direção selecionada no rascunho. Salve o storyboard para registrar a escolha.");
  };
  const saveBoard=()=>void run("storyboard",async()=>{
    if(!board||!directions||!briefRow)throw new Error("Salve o brief e gere uma direção antes do storyboard.");
    if(directions.status!=="CURRENT")throw new Error("As direções estão desatualizadas. Gere novas propostas primeiro.");
    if(briefDirty)throw new Error("Salve primeiro as alterações do brief.");
    if(board.duration_ms!==briefRow.content.duration_ms||board.fps!==briefRow.content.fps)throw new Error("Duração/FPS do storyboard diferem do brief. Ajuste os planos antes de salvar.");
    if(!board.shots.length||board.shots.some((shot)=>shot.beat.trim().length<3||shot.visual_description.trim().length<8))throw new Error("Cada plano precisa de beat (3 caracteres) e descrição visual (8 caracteres).");
    if(board.shots.reduce((sum,shot)=>sum+shot.duration_ms,0)!==board.duration_ms)throw new Error("Os planos devem preencher exatamente a duração do brief.");
    const saved=await api.saveCreativeStoryboard(project.id,boardRow?.revision??0,directions.revision,{...board,shots:sequence(board.shots)});
    setBoardRow(saved);setBoard(saved.content);setReview(await api.creativeReview(project.id));
  });
  const decide=(decision:"APPROVE"|"REVISE"|"REJECT")=>void run("review",async()=>{
    if(!boardRow||!review)throw new Error("Salve o storyboard e carregue a revisão antes de decidir.");
    if(boardDirty)throw new Error("Salve o storyboard antes de registrar a decisão.");
    if(actor.trim().length<2)throw new Error("Informe o nome do responsável pela revisão.");
    const saved=await api.decideCreative(project.id,{expected_revision:review.review?.revision??0,expected_storyboard_revision:boardRow.revision,expected_snapshot_sha256:review.current_snapshot_sha256,decision,actor:actor.trim(),notes,storyboard_reviewed:checks.storyboard,rights_checked:checks.rights,facts_checked:checks.facts});
    setReview(saved);setChecks({storyboard:false,rights:false,facts:false});
  });

  const briefDirty=JSON.stringify(brief)!==JSON.stringify(briefRow?.content??initialBrief(project));
  const dnaDirty=JSON.stringify(dna)!==JSON.stringify(dnaRow?.content??emptyDNA);
  const boardDirty=JSON.stringify(board)!==JSON.stringify(boardRow?.content??null);
  const dirty=briefDirty||dnaDirty||boardDirty;
  const adoptServer=()=>{
    setBrief(briefRow?.content??initialBrief(project));setDna(dnaRow?.content??emptyDNA);
    setBoard(boardRow?.content??null);setConflict(false);setConflictLoaded(false);setError("");
    setRestrictionsText(lines(briefRow?.content.restrictions??[]));setMustHaveText(lines(dnaRow?.content.must_have??[]));setAvoidText(lines(dnaRow?.content.avoid??[]));
    setNotice("Versão do servidor carregada. O rascunho anterior foi descartado por sua escolha.");
  };
  const applyDraft=()=>{
    setConflict(false);setConflictLoaded(false);setError("");
    setNotice("Rascunho local mantido. Ao salvar, ele substituirá a revisão atual do servidor.");
  };
  const updateShot=(id:string,patch:Partial<StoryboardShot>)=>setBoard((current)=>current?{...current,shots:current.shots.map((shot)=>shot.id===id?{...shot,...patch}:shot)}:current);
  const resizeDraftShot=(index:number,value:number)=>setBoard((current)=>current?resizeShot(current,index,value):current);
  const splitDraftShot=(index:number)=>setBoard((current)=>current?splitShot(current,index):current);
  const removeDraftShot=(index:number)=>setBoard((current)=>current?removeShot(current,index):current);
  const moveDraftShot=(index:number,offset:-1|1)=>setBoard((current)=>current?moveShot(current,index,offset):current);
  const syncDraftDuration=()=>setBoard((current)=>current&&briefRow?syncDuration(current,briefRow.content.duration_ms,briefRow.content.fps):current);

  if(loading)return <section className="creative-shell" aria-busy="true"><p role="status">Carregando revisões criativas…</p></section>;
  return <section className="creative-shell" aria-label="Creative Director">
    <div className="creative-hero"><div><span className="creative-kicker">ATELIER OS / CREATIVE DIRECTOR</span><h2>Da intenção ao quadro.</h2><p>Direção visual e revisão editorial persistidas para <strong>{project.title}</strong>.</p><button type="button" className="creative-refresh" disabled={!!busy} onClick={()=>void refreshRevision()}><RefreshCw size={14}/> Atualizar estado salvo</button></div><span className="creative-project-mark">{channel.name}<small>{project.format.toUpperCase()} · {project.content_type.toUpperCase()}</small></span></div>
    <nav className="creative-steps" aria-label="Etapas criativas">{steps.map((item,index)=><button key={item.id} type="button" className={step===item.id?"active":""} aria-current={step===item.id?"step":undefined} onClick={()=>setStep(item.id)}><span>{String(index+1).padStart(2,"0")}</span>{item.label}</button>)}</nav>
    {dirty&&<p className="creative-dirty">Há alterações locais não salvas{briefDirty?" · brief":""}{dnaDirty?" · DNA":""}{boardDirty?" · storyboard":""}.</p>}
    {error&&<div className="creative-error" role="alert"><AlertTriangle size={17}/><span>{error}</span>{conflict&&!conflictLoaded&&<button type="button" onClick={()=>void refreshRevision()} disabled={!!busy}><RefreshCw size={15}/> Atualizar revisões sem perder o rascunho</button>}</div>}
    {conflictLoaded&&<div className="creative-conflict" role="alert"><strong>Outra gravação alterou o servidor.</strong><p>O rascunho local foi mantido. Carregue a revisão do servidor ou decida substituí-la explicitamente. A aplicação do rascunho pode remover alterações feitas por outra pessoa.</p><button type="button" onClick={adoptServer}>Carregar versão do servidor</button><button type="button" onClick={applyDraft}>Aplicar meu rascunho sobre a revisão atual</button></div>}
    {notice&&<p className="creative-notice" role="status"><Check size={16}/>{notice}</p>}
    {step==="brief"&&<div className="creative-panel"><div className="creative-panel-head"><div><span>01 / INTENÇÃO</span><h3>Brief criativo</h3><p>O projeto existente define o formato. O restante é declarado e revisado por você.</p></div><span>REV {briefRow?.revision??0}</span></div>
      <div className="creative-fields"><label>Tópico<input value={brief.topic} minLength={3} maxLength={500} onChange={(e)=>setBrief({...brief,topic:e.target.value})}/></label><label>Público<input value={brief.audience} minLength={2} maxLength={240} onChange={(e)=>setBrief({...brief,audience:e.target.value})}/></label><label className="wide">Objetivo<textarea value={brief.objective} minLength={5} maxLength={600} onChange={(e)=>setBrief({...brief,objective:e.target.value})}/></label><label>Formato<input value={brief.format} readOnly title="Formato definido pelo projeto"/></label><label>Duração (ms)<input type="number" min={3000} max={600000} step={1} value={brief.duration_ms} onChange={(e)=>setBrief({...brief,duration_ms:Number(e.target.value)})}/></label><label>FPS<select value={brief.fps} onChange={(e)=>setBrief({...brief,fps:Number(e.target.value) as CreativeBrief["fps"]})}>{[24,25,30,60].map((fps)=><option key={fps}>{fps}</option>)}</select></label><label>Idioma<input value={brief.language} minLength={2} maxLength={16} onChange={(e)=>setBrief({...brief,language:e.target.value})}/></label><label>Modo factual<select value={brief.factual_mode} onChange={(e)=>setBrief({...brief,factual_mode:e.target.value as CreativeBrief["factual_mode"]})}><option value="FACT_CHECK_REQUIRED">Fatos exigem fontes revisadas</option><option value="FICTIONAL">Ficcional</option></select></label><label className="wide">Estilo e intenção<textarea value={brief.style_notes} maxLength={2000} onChange={(e)=>setBrief({...brief,style_notes:e.target.value})}/></label><label className="wide">Restrições (uma por linha)<textarea value={restrictionsText} onChange={(e)=>{setRestrictionsText(e.target.value);setBrief({...brief,restrictions:list(e.target.value)});}}/></label></div>
      <div className="creative-subhead"><h4>Fontes declaradas</h4><button type="button" onClick={()=>setBrief({...brief,sources:[...brief.sources,{url:"",title:"",fact_reviewed:false}]})}><Plus size={15}/> Fonte</button></div><p className="creative-help">A confirmação de uma fonte indica revisão humana; não verifica fatos automaticamente.</p>{brief.sources.map((source,index)=><div className="creative-source" key={index}><label>URL<input type="url" value={source.url} onChange={(e)=>setBrief({...brief,sources:brief.sources.map((item,i)=>i===index?{...item,url:e.target.value}:item)})}/></label><label>Título<input value={source.title} onChange={(e)=>setBrief({...brief,sources:brief.sources.map((item,i)=>i===index?{...item,title:e.target.value}:item)})}/></label><label className="creative-check"><input type="checkbox" checked={source.fact_reviewed} onChange={(e)=>setBrief({...brief,sources:brief.sources.map((item,i)=>i===index?{...item,fact_reviewed:e.target.checked}:item)})}/> Fonte revisada</label><button type="button" aria-label={`Remover fonte ${index+1}`} onClick={()=>setBrief({...brief,sources:brief.sources.filter((_,i)=>i!==index)})}><Trash2 size={15}/></button></div>)}
      <div className="creative-subhead"><h4>Assets do brief</h4><span>{brief.asset_ids.length} selecionados</span></div>{assets.length?<div className="creative-options">{assets.map((asset)=><label key={asset.id}><input type="checkbox" checked={brief.asset_ids.includes(asset.id)} onChange={(e)=>setBrief({...brief,asset_ids:e.target.checked?[...brief.asset_ids,asset.id]:brief.asset_ids.filter((id)=>id!==asset.id)})}/>{asset.name}<small>{asset.rights_status}</small></label>)}</div>:<p className="creative-help">Nenhum asset na biblioteca. O brief pode usar somente texto.</p>}
      <div className="creative-actions"><button type="button" className="creative-primary" disabled={!!busy||conflict||!briefDirty} onClick={saveBrief}><Save size={16}/>{busy==="brief"?"Salvando…":"Salvar brief"}</button></div></div>}
    {step==="dna"&&<div className="creative-panel"><div className="creative-panel-head"><div><span>02 / IDENTIDADE DO CANAL</span><h3>Creative DNA</h3><p>{channel.name} · regras compartilhadas pelos projetos deste canal.</p></div><span>REV {dnaRow?.revision??0}</span></div><p className="creative-warning"><AlertTriangle size={17}/> Alterar este DNA pode invalidar direções e aprovações de vários projetos do canal.</p><div className="creative-fields"><label>Tipografia de destaque<input value={dna.font_display} onChange={(e)=>setDna({...dna,font_display:e.target.value})}/></label><label>Tipografia de texto<input value={dna.font_body} onChange={(e)=>setDna({...dna,font_body:e.target.value})}/></label><label className="wide">Tom editorial<input value={dna.tone} onChange={(e)=>setDna({...dna,tone:e.target.value})}/></label><label>Energia<select value={dna.energy} onChange={(e)=>setDna({...dna,energy:e.target.value as CreativeDNA["energy"]})}><option value="restrained">Contida</option><option value="balanced">Equilibrada</option><option value="intense">Intensa</option></select></label><label>Máximo de palavras por cartão<input type="number" min={1} max={40} value={dna.max_words_per_card} onChange={(e)=>setDna({...dna,max_words_per_card:Number(e.target.value)})}/></label><label className="wide">Obrigatório (um por linha)<textarea value={mustHaveText} onChange={(e)=>{setMustHaveText(e.target.value);setDna({...dna,must_have:list(e.target.value)});}}/></label><label className="wide">Evitar (um por linha)<textarea value={avoidText} onChange={(e)=>{setAvoidText(e.target.value);setDna({...dna,avoid:list(e.target.value)});}}/></label></div><div className="creative-subhead"><h4>Paleta</h4><button type="button" disabled={dna.palette.length>=8} onClick={()=>setDna({...dna,palette:[...dna.palette,"#D0E5BC"]})}><Plus size={15}/> Cor</button></div><div className="creative-palette-editor">{dna.palette.map((color,index)=><label key={index}><input type="color" value={color} onChange={(e)=>setDna({...dna,palette:dna.palette.map((item,i)=>i===index?e.target.value:item)})}/><input aria-label={`Cor ${index+1} em hexadecimal`} pattern="#[0-9a-fA-F]{6}" value={color} onChange={(e)=>setDna({...dna,palette:dna.palette.map((item,i)=>i===index?e.target.value:item)})}/><button type="button" aria-label={`Remover cor ${index+1}`} disabled={dna.palette.length<=2} onClick={()=>setDna({...dna,palette:dna.palette.filter((_,i)=>i!==index)})}><Trash2 size={14}/></button></label>)}</div><div className="creative-actions"><button type="button" className="creative-primary" disabled={!!busy||conflict||!dnaDirty} onClick={saveDNA}><Save size={16}/>{busy==="dna"?"Salvando…":"Salvar DNA"}</button></div></div>}
    {step==="directions"&&<div className="creative-panel"><div className="creative-panel-head"><div><span>03 / EXPLORAÇÃO</span><h3>Três direções</h3><p>Propostas determinísticas de referência, geradas apenas a partir do brief e DNA salvos.</p></div><span>{directions?.status??"SEM PROPOSTAS"}</span></div><div className="creative-actions top"><button type="button" className="creative-primary" disabled={!!busy||conflict||!briefRow||!dnaRow||briefDirty||dnaDirty} onClick={generate}><Plus size={16}/>{busy==="directions"?"Gerando…":directions?.status==="STALE"?"Regenerar propostas":"Gerar / consultar propostas"}</button></div>{(!briefRow||!dnaRow)&&<p className="creative-warning">Salve o brief e o DNA do canal primeiro.</p>}{directions?.status==="STALE"&&<p className="creative-warning">As propostas usam revisões anteriores. Regere após salvar brief e DNA.</p>}{directions&&<><p className="creative-origin">ORIGEM: {directions.origin} · REV {directions.revision} · nenhuma imagem ou IA audiovisual foi gerada</p><div className="creative-directions">{directions.content.directions.map((direction,index)=><article key={direction.id} className={board?.direction_id===direction.id?"chosen":""}><span className="creative-card-index">{String(index+1).padStart(2,"0")} / {direction.estimated_complexity}</span><h4>{direction.title}</h4><p className="creative-thesis">{direction.thesis}</p><dl><dt>Por quê</dt><dd>{direction.rationale}</dd><dt>Curva emocional</dt><dd>{direction.emotional_arc}</dd><dt>Ritmo</dt><dd>{direction.rhythm}</dd><dt>Tipografia</dt><dd>{direction.typography}</dd><dt>Composição</dt><dd>{direction.composition}</dd><dt>Movimento</dt><dd>{direction.motion_language}</dd></dl><div className="creative-swatches" aria-label={`Paleta da direção ${direction.title}`}>{direction.palette.map((color,i)=><span key={i} style={{backgroundColor:color}} title={color}/>)}</div><button type="button" disabled={directions.status!=="CURRENT"} onClick={()=>chooseDirection(direction.id)}>{board?.direction_id===direction.id?"Direção no storyboard":"Selecionar para storyboard"}</button></article>)}</div></>}</div>}
    {step==="storyboard"&&<div className="creative-panel"><div className="creative-panel-head"><div><span>04 / PLANEJAMENTO VISUAL</span><h3>Storyboard</h3><p>Planos e intenções. Esta régua não reproduz nem renderiza vídeo.</p></div><span>{boardRow?`REV ${boardRow.revision} · ${boardRow.status}`:"RASCUNHO"}</span></div>{!board?<p className="creative-help">Selecione uma direção atual na etapa anterior para criar o primeiro plano.</p>:<><p className="creative-origin">DIREÇÃO {board.direction_id} · {ms(board.duration_ms)} · {board.fps} FPS · {board.shots.length} PLANOS</p><div className="creative-ruler" role="group" aria-label="Régua proporcional de planos">{board.shots.map((shot,index)=><div key={shot.id} style={{width:`${shot.duration_ms/board.duration_ms*100}%`}} title={`Plano ${index+1}: ${ms(shot.start_ms)}–${ms(shot.start_ms+shot.duration_ms)}`}><span>{index+1}</span></div>)}</div><div className="creative-ruler-label"><span>0 s</span><span>{ms(board.duration_ms)}</span></div>{board.duration_ms!==briefRow?.content.duration_ms&&<div className="creative-warning">O brief salvo tem {ms(briefRow?.content.duration_ms??0)}. Ajuste a duração antes de salvar. <button type="button" onClick={syncDraftDuration} disabled={board.shots.at(-1)!.duration_ms+(briefRow?.content.duration_ms??0)-board.duration_ms<1}>Ajustar último plano ao brief</button></div>}{board.shots.map((shot,index)=><article className="creative-shot" key={shot.id}><div className="creative-shot-head"><span>PLANO {String(index+1).padStart(2,"0")} · {ms(shot.start_ms)} → {ms(shot.start_ms+shot.duration_ms)}</span><div><button type="button" aria-label={`Mover plano ${index+1} para cima`} disabled={index===0} onClick={()=>moveDraftShot(index,-1)}><ArrowUp size={15}/></button><button type="button" aria-label={`Mover plano ${index+1} para baixo`} disabled={index===board.shots.length-1} onClick={()=>moveDraftShot(index,1)}><ArrowDown size={15}/></button><button type="button" aria-label={`Dividir plano ${index+1}`} disabled={board.shots.length>=100||shot.duration_ms<2} onClick={()=>splitDraftShot(index)}><Plus size={15}/></button><button type="button" aria-label={`Remover plano ${index+1}`} disabled={board.shots.length===1} onClick={()=>removeDraftShot(index)}><Trash2 size={15}/></button></div></div><div className="creative-fields"><label>Início (ms)<input value={shot.start_ms} readOnly/></label><label>Duração (ms){index<board.shots.length-1?<input type="number" min={1} max={shot.duration_ms+board.shots[index+1].duration_ms-1} value={shot.duration_ms} onChange={(e)=>resizeDraftShot(index,Number(e.target.value))}/>:<input value={shot.duration_ms} readOnly title="Ajuste o plano anterior para redistribuir a duração"/>}</label><label>Beat<input value={shot.beat} minLength={3} maxLength={240} onChange={(e)=>updateShot(shot.id,{beat:e.target.value})}/></label><label>Texto na tela<input value={shot.on_screen_text} maxLength={160} onChange={(e)=>updateShot(shot.id,{on_screen_text:e.target.value})}/></label><label className="wide">Descrição visual<textarea value={shot.visual_description} minLength={8} maxLength={1000} onChange={(e)=>updateShot(shot.id,{visual_description:e.target.value})}/></label><label>Câmera<input value={shot.camera_intent} minLength={2} maxLength={200} onChange={(e)=>updateShot(shot.id,{camera_intent:e.target.value})}/></label><label>Movimento<input value={shot.motion_intent} minLength={2} maxLength={200} onChange={(e)=>updateShot(shot.id,{motion_intent:e.target.value})}/></label><label className="wide">Indicação de áudio<input value={shot.audio_cue} maxLength={200} onChange={(e)=>updateShot(shot.id,{audio_cue:e.target.value})}/></label></div><details><summary>Assets e alegações do plano</summary><div className="creative-options">{assets.filter((asset)=>brief.asset_ids.includes(asset.id)).map((asset)=><label key={asset.id}><input type="checkbox" checked={shot.asset_ids.includes(asset.id)} onChange={(e)=>updateShot(shot.id,{asset_ids:e.target.checked?[...shot.asset_ids,asset.id]:shot.asset_ids.filter((id)=>id!==asset.id)})}/>{asset.name}<small>{asset.rights_status}</small></label>)}{claims.filter((claim)=>claim.status!=="REMOVED").map((claim)=><label key={claim.id}><input type="checkbox" checked={shot.claim_ids.includes(claim.id)} onChange={(e)=>updateShot(shot.id,{claim_ids:e.target.checked?[...shot.claim_ids,claim.id]:shot.claim_ids.filter((id)=>id!==claim.id)})}/>{claim.text}<small>{claim.status}</small></label>)}{!assets.some((asset)=>brief.asset_ids.includes(asset.id))&&!claims.length&&<p>Sem assets ou alegações disponíveis.</p>}</div></details></article>)}<div className="creative-actions"><button type="button" className="creative-primary" disabled={!!busy||conflict||!boardDirty||directions?.status!=="CURRENT"} onClick={saveBoard}><Save size={16}/>{busy==="storyboard"?"Salvando…":"Salvar storyboard"}</button></div></>}</div>}
    {step==="review"&&<div className="creative-panel"><div className="creative-panel-head"><div><span>05 / DECISÃO HUMANA</span><h3>Revisão criativa</h3><p>Esta decisão cobre o storyboard salvo. MP4, animatic e publicação exigem revisão própria.</p></div><span className="creative-status">{review?.status??"SEM STORYBOARD"}</span></div>{!review?<p className="creative-help">Salve um storyboard para consultar o snapshot de revisão.</p>:<><div className="creative-review-summary"><div><span>STATUS</span><strong>{review.status}</strong></div><div><span>STORYBOARD</span><strong>REV {boardRow?.revision??0}</strong></div><div><span>SNAPSHOT SHA-256</span><code>{review.current_snapshot_sha256}</code></div></div>{review.blockers.length>0&&<div className="creative-blockers"><strong>Bloqueios do backend</strong><ul>{review.blockers.map((blocker,index)=><li key={index}>{blocker}</li>)}</ul></div>}{review.status==="STALE"&&<p className="creative-warning">Uma dependência mudou desde a última decisão: brief, DNA, direção, plano/EDL, rights, claims ou storyboard. Confira as revisões e decida novamente.</p>}{review.review&&<p className="creative-help">Última decisão: {review.review.decision} por {review.review.actor} · revisão {review.review.revision} · {new Date(review.review.created_at).toLocaleString("pt-BR")}</p>}<div className="creative-fields"><label>Responsável<input value={actor} maxLength={120} onChange={(e)=>setActor(e.target.value)} placeholder="Nome de quem revisou"/></label><label className="wide">Notas da decisão<textarea value={notes} maxLength={2000} onChange={(e)=>setNotes(e.target.value)}/></label></div><div className="creative-review-checks"><label><input type="checkbox" checked={checks.storyboard} onChange={(e)=>setChecks({...checks,storyboard:e.target.checked})}/> Revisei todos os planos do storyboard</label><label><input type="checkbox" checked={checks.rights} onChange={(e)=>setChecks({...checks,rights:e.target.checked})}/> Conferi os direitos dos assets usados</label><label><input type="checkbox" checked={checks.facts} onChange={(e)=>setChecks({...checks,facts:e.target.checked})}/> Conferi alegações e fontes factuais</label></div><div className="creative-actions"><button type="button" className="creative-primary" disabled={!!busy||conflict||!!review.blockers.length||!checks.storyboard||!checks.rights||!checks.facts||boardDirty||actor.trim().length<2} onClick={()=>decide("APPROVE")}>Aprovar storyboard</button><button type="button" disabled={!!busy||conflict||boardDirty||actor.trim().length<2} onClick={()=>decide("REVISE")}>Solicitar revisão</button><button type="button" disabled={!!busy||conflict||boardDirty||actor.trim().length<2} onClick={()=>decide("REJECT")}>Rejeitar</button></div></>}</div>}
    {step==="review"&&<CreativeMotionProof projectId={project.id} revision={boardRow?.revision??0}
      review={review} assets={assets} dirty={boardDirty||briefDirty||dnaDirty}/>}
  </section>;
}
