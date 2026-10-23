"use client";

import {useEffect, useState} from "react";
import {api} from "@/lib/api";
import {desktopChooseBlender, runningInDesktop} from "@/lib/desktop";

type State={available:boolean;path:string|null;required_version:string};
function message(error:unknown){return error instanceof Error?error.message:String(error);}

export function BlenderSettingsPanel(){
  const [state,setState]=useState<State|null>(null);
  const [path,setPath]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  useEffect(()=>{void api.blenderStatus().then((value)=>{setState(value);setPath(value.path??"");})
    .catch((reason)=>setError(message(reason)));},[]);
  const save=async(chosen:string)=>{
    setBusy(true);setError(null);
    try{const value=await api.setBlender(chosen);setState(value);setPath(value.path);}
    catch(reason){setError(message(reason));}finally{setBusy(false);}
  };
  const choose=async()=>{try{const selected=await desktopChooseBlender();if(selected)await save(selected);}
    catch(reason){setError(message(reason));}};
  return <section className="panel"><div className="panel-head"><div><h3>Blender para narrativa 3D</h3>
    <p>Dependência opcional no desktop. O render 3D usa Blender 4.5 LTS em background; o MediaGrid não baixa nem instala o programa automaticamente.</p>
  </div></div><div className="panel-body">
    <p className="small-note">Estado: {state?.available?"disponível":"indisponível"} · Versão exigida: {state?.required_version??"4.5 LTS"}</p>
    {state?.path&&<p className="small-note">Executável: {state.path}</p>}
    {runningInDesktop()?<button className="button" disabled={busy} onClick={()=>void choose()}>Escolher blender.exe</button>
      :<div className="field-grid"><label className="field">Caminho local do blender.exe<input value={path} onChange={(event)=>setPath(event.target.value)} placeholder="C:\\Tools\\blender-4.5\\blender.exe"/></label>
        <button className="button" disabled={busy||!path.trim()} onClick={()=>void save(path.trim())}>Validar e salvar</button></div>}
    {error&&<p role="alert" className="alert">{error}</p>}
    <p className="small-note">Sem Blender compatível, o job fica WAITING_FOR_WORKER. Após configurar, use “Renderizar blocking” novamente para liberar o mesmo job.</p>
  </div></section>;
}
