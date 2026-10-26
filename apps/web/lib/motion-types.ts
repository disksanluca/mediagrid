export interface MotionRecipeInfo {
  id:string;version:string;sha256:string;status:string;
  canvas:{width:number;height:number;fps_num:number;fps_den:number};
  asset_slots:Record<string,"audio"|"image"|"video">;
  shots:Array<{slot:string;reference_duration_ms:number}>;
}
export type MotionEngineRequest = import("../../../contracts/motion/generated/motion-contracts").EngineRequest;
export interface MotionArtifactReview {
  blockers:string[];
  status:string;revision:number;plan_sha256:string;video_sha256:string;publication_enabled:false;
  history:Array<{revision:number;decision:string;actor:string;notes:string;video_sha256:string;created_at:string}>;
}
