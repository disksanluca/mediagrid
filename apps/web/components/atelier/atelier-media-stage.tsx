import {Film} from "lucide-react";
import {api} from "@/lib/api";
import type {Channel, Engine, Job, Project, Scene} from "@/lib/types";

interface Props {
  project: Project | undefined;
  channel: Channel | undefined;
  engine: Engine;
  scene: Scene | undefined;
  sceneIndex: number;
  motionJob?: Job | null;
}

export function AtelierMediaStage({project, channel, engine, scene, sceneIndex, motionJob}: Props) {
  const rendered = project?.status === "QC" || project?.status === "APPROVED";
  const hasVideo = rendered || !!motionJob;
  const sceneCount = project?.plan?.scenes.length ?? 0;
  return <div className="atelier-media-frame">
    {hasVideo && project ? <video className="atelier-stage-video" controls preload="metadata"
      src={rendered ? api.output(project.id) : api.creativeMotionVideo(project.id, motionJob!.id)}
      aria-label={`Vídeo renderizado de ${project.title}`}/> : <div className="atelier-stage-preview">
      <div className="atelier-stage-grid" aria-hidden="true"/>
      <span className="atelier-stage-watermark" aria-hidden="true">MG</span>
      <div className="atelier-stage-hud">MG / {engine.toUpperCase()}<br/>{project?.format.toUpperCase() ?? "PROJETO LOCAL"}<br/>{sceneCount ? `${String(sceneIndex + 1).padStart(2, "0")} / ${String(sceneCount).padStart(2, "0")}` : "SEM CENAS"}</div>
      <div className="atelier-stage-copy">
        <span className="eyebrow">{channel?.name ?? "MEDIAGRID ATELIER"} / {scene ? `CENA ${String(sceneIndex + 1).padStart(2, "0")}` : "ESPAÇO CRIATIVO"}</span>
        <h3>{scene?.on_screen_text || project?.title || "Sua próxima história começa aqui."}</h3>
        <p>{scene?.narration || project?.topic || "Crie um canal e uma pauta para preparar sua primeira produção local."}</p>
        <span className="atelier-stage-rule" aria-hidden="true"/>
      </div>
      <div className="atelier-stage-caption"><Film size={14} strokeWidth={1.75}/> PRÉVIA EDITORIAL / NÃO É VÍDEO RENDERIZADO</div>
    </div>}
    {!hasVideo && <div className="atelier-stage-transport"><span><Film size={15} strokeWidth={1.75}/> PLANO</span><span>{sceneCount} {sceneCount === 1 ? "CENA" : "CENAS"} / {project?.plan?.target_duration_seconds ?? 0}s ESTIMADOS</span><span>RENDER DISPONÍVEL NO EDITOR</span></div>}
  </div>;
}
