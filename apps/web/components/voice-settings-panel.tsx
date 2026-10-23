"use client";

import {useEffect, useState} from "react";
import {Mic, Save} from "lucide-react";
import {api} from "@/lib/api";

type VoiceStatus = {available:boolean;voices:string[];voice_name:string|null;rate:number};

export function VoiceSettingsPanel({mode}:{mode:string}) {
  const [status,setStatus]=useState<VoiceStatus|null>(null);
  const [voice,setVoice]=useState("");
  const [rate,setRate]=useState(0);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState<string|null>(null);
  useEffect(()=>{
    if(mode!=="LOCAL")return;
    void api.voiceStatus().then((value)=>{
      setStatus(value);setVoice(value.voice_name??value.voices[0]??"");setRate(value.rate);
    }).catch((reason)=>setMessage(reason instanceof Error?reason.message:"Falha ao consultar as vozes."));
  },[mode]);
  if(mode!=="LOCAL")return null;
  const save=async()=>{
    setBusy(true);setMessage(null);
    try {
      const value=await api.setVoice(voice,rate);
      setStatus(value);
      setMessage("Voz salva. Gere a voz novamente nos projetos que desejar atualizar.");
    } catch(reason) {setMessage(reason instanceof Error?reason.message:"Não foi possível salvar a voz.");}
    finally {setBusy(false);}
  };
  return <section className="panel"><div className="panel-head"><div><h3>Voz do estúdio</h3><p>Escolha uma voz pt-BR instalada no Windows e ajuste a velocidade da próxima narração.</p></div><Mic size={19}/></div><div className="panel-body">
    {!status?<p className="small-note">Consultando vozes locais…</p>:status.voices.length===0?<p className="small-note">Nenhuma voz pt-BR compatível encontrada. Instale uma voz no Windows para gerar narrações.</p>:<><div className="field-grid"><label className="field">Voz<select value={voice} onChange={(event)=>setVoice(event.target.value)}>{status.voices.map((name)=><option key={name} value={name}>{name}</option>)}</select></label><label className="field">Velocidade (-5 a 5)<input type="number" min="-5" max="5" step="1" value={rate} onChange={(event)=>setRate(Number(event.target.value))}/></label></div><p className="small-note">A escolha afeta apenas novas gerações. Ouça o WAV e o MP4 inteiro antes de aprovar; a qualidade depende da voz instalada.</p><button className="button" disabled={busy||!voice||!Number.isInteger(rate)||rate<-5||rate>5} onClick={()=>void save()}><Save size={15}/> Salvar voz</button></>}
    {message&&<p className="small-note">{message}</p>}
  </div></section>;
}
