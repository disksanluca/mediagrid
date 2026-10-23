"use client";

import {useEffect, useRef, useState} from "react";
import {Mic, Square, Upload} from "lucide-react";
import {api} from "@/lib/api";

export function RecordedVoicePanel({projectId,disabled,onRun}:{
  projectId:string;
  disabled:boolean;
  onRun:(action:()=>Promise<unknown>)=>Promise<void>;
}) {
  const [file,setFile]=useState<File|null>(null);
  const [preview,setPreview]=useState<string|null>(null);
  const [recording,setRecording]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [notice,setNotice]=useState<string|null>(null);
  const [rights,setRights]=useState(false);
  const [script,setScript]=useState(false);
  const recorder=useRef<MediaRecorder|null>(null);
  const stream=useRef<MediaStream|null>(null);
  const limit=useRef<number|null>(null);

  useEffect(()=>{
    if(!file){setPreview(null);return;}
    const url=URL.createObjectURL(file);
    setPreview(url);
    return()=>URL.revokeObjectURL(url);
  },[file]);
  useEffect(()=>()=>{
    if(limit.current!==null)window.clearTimeout(limit.current);
    if(recorder.current?.state==="recording")recorder.current.stop();
    stream.current?.getTracks().forEach((track)=>track.stop());
  },[]);

  const begin=async()=>{
    setError(null);
    setNotice(null);
    if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==="undefined"){
      setError("Gravação indisponível neste navegador. Importe um arquivo de áudio.");
      return;
    }
    try{
      const captured=await navigator.mediaDevices.getUserMedia({audio:true});
      stream.current=captured;
      const mime=MediaRecorder.isTypeSupported("audio/webm;codecs=opus")?"audio/webm;codecs=opus":undefined;
      const current=new MediaRecorder(captured,mime?{mimeType:mime}:undefined);
      const chunks:BlobPart[]=[];
      current.ondataavailable=(event)=>{if(event.data.size)chunks.push(event.data);};
      current.onstop=()=>{
        if(limit.current!==null)window.clearTimeout(limit.current);
        captured.getTracks().forEach((track)=>track.stop());
        stream.current=null;
        setRecording(false);
        const type=current.mimeType||"audio/webm";
        const extension=type.includes("mp4")?"m4a":type.includes("ogg")?"ogg":"webm";
        const capturedFile=new File(chunks,`narracao-propria.${extension}`,{type});
        if(capturedFile.size)setFile(capturedFile);
        else setError("O microfone não capturou áudio. Tente novamente.");
      };
      current.onerror=()=>setError("Falha ao gravar. Você pode importar um arquivo de áudio.");
      recorder.current=current;
      setFile(null);
      current.start(1000);
      setRecording(true);
      limit.current=window.setTimeout(()=>current.state==="recording"&&current.stop(),300000);
    }catch(reason){
      stream.current?.getTracks().forEach((track)=>track.stop());
      stream.current=null;
      setError(reason instanceof Error?`Microfone indisponível: ${reason.message}`:"Microfone indisponível.");
    }
  };
  const submit=()=>onRun(async()=>{
    if(!file)return;
    await api.importRecordedVoice(projectId,file,rights,script);
    setNotice("Narração importada. Ouça o WAV e renderize novamente para conferir o vídeo.");
    setFile(null);
    setRights(false);
    setScript(false);
  });

  return <div className="recorded-voice-panel">
    <p className="small-note">Sua própria voz pode substituir a voz sintética no próximo render. Grave aqui ou importe até 5 minutos / 50 MB. Ouça e confirme que acompanha o roteiro salvo; o sistema não alinha as palavras automaticamente.</p>
    <div className="recorded-voice-actions">
      <button className="button full" type="button" disabled={disabled&&!recording} onClick={()=>recording?recorder.current?.stop():void begin()}>
        {recording?<><Square size={15}/> Parar gravação</>:<><Mic size={15}/> Gravar no microfone</>}
      </button>
      <label className="button full"><Upload size={15}/> Importar áudio
        <input type="file" accept="audio/*,.wav,.mp3,.m4a,.webm,.ogg" disabled={disabled||recording}
          onChange={(event)=>{setFile(event.target.files?.[0]??null);setError(null);setNotice(null);event.target.value="";}}/>
      </label>
    </div>
    {recording&&<p role="status" className="small-note">Gravando. Pare para ouvir antes de importar.</p>}
    {error&&<p role="alert" className="small-note">{error}</p>}
    {notice&&<p role="status" className="small-note">{notice}</p>}
    {file&&<><p className="small-note">Selecionado: {file.name} · {(file.size/1024/1024).toFixed(1)} MB</p>
      {preview&&<audio controls preload="metadata" src={preview} aria-label="Ouvir narração selecionada"/>}
      <div className="review-checks"><label><input type="checkbox" checked={rights} onChange={(event)=>setRights(event.target.checked)}/> Tenho os direitos desta gravação</label><label><input type="checkbox" checked={script} onChange={(event)=>setScript(event.target.checked)}/> A gravação corresponde ao roteiro salvo</label></div>
      <button className="button primary full" disabled={disabled||!rights||!script||file.size>50*1024*1024} onClick={()=>void submit()}>Usar esta narração no projeto</button>
    </>}
  </div>;
}
