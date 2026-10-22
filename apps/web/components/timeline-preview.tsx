"use client";

import {Player} from "@remotion/player";
import {useEffect, useState} from "react";
import {MediaGridTimelineV2} from "../../renderer/src/timeline-v2";
import {api} from "../lib/api";
import type {PreviewResponse, TimelineResponse} from "../lib/types";

export function TimelinePreview({projectId,timeline}:{projectId:string;timeline:TimelineResponse}) {
  const [preview,setPreview]=useState<PreviewResponse|null>(null);
  const [error,setError]=useState<string|null>(null);
  useEffect(()=>{
    let cancelled=false;
    setPreview(null);
    setError(null);
    void api.preview(projectId).then((value)=>{
      if(!cancelled)setPreview(value);
    }).catch((reason)=>{
      if(!cancelled)setError(reason instanceof Error?reason.message:String(reason));
    });
    return()=>{cancelled=true;};
  },[projectId,timeline.revision,timeline.legacy_sha256]);
  const canvas=timeline.edl.canvas;
  const fps=canvas.fps_num/canvas.fps_den;
  const props=preview?{
    ...preview.props,
    scenes:preview.props.scenes.map((scene)=>scene.media_file?{
      ...scene,media_file:api.assetFile(scene.media_file),
    }:scene),
    sounds:preview.props.sounds?.map((item)=>({
      ...item,media_file:api.assetFile(item.media_file),
    })),
    video_layers:preview.props.video_layers?.map((item)=>({
      ...item,media_file:api.assetFile(item.media_file),
    })),
    voice_file:preview.voice_ready?api.voiceFile(projectId):undefined,
  }:null;
  return <section className="panel timeline-preview"><div className="panel-head"><div><h3>Prévia antes do render</h3><p>Composição visual da revisão salva, reproduzida pelo mesmo Remotion do MP4.</p></div>{preview&&<span className="badge">REV {preview.revision}</span>}</div><div className="panel-body">
    {error&&<p className="small-note" role="alert">Prévia indisponível: {error}</p>}
    {!error&&!props&&<p className="small-note">Validando mídia e preparando a prévia local…</p>}
    {props&&<><div className="timeline-preview-player" style={{aspectRatio:`${canvas.width}/${canvas.height}`}}><Player
      key={`${projectId}-${preview?.revision}-${preview?.revision_sha256}`}
      component={MediaGridTimelineV2}
      inputProps={props}
      durationInFrames={Math.max(1,Math.round(preview!.duration_seconds*fps))}
      compositionWidth={canvas.width}
      compositionHeight={canvas.height}
      fps={fps}
      controls
      style={{width:"100%",height:"100%"}}
    /></div><p className="small-note">{preview?.voice_ready?"Voz local incluída na prévia. O mix final recebe limitador FFmpeg; ouça o MP4 antes de aprovar.":"A voz ainda não foi gerada. Gere a voz local para conferir a duração e o áudio finais."} A prévia representa a revisão salva; alterações em edição exigem salvar.</p></>}
  </div></section>;
}
