import type {CreativeStoryboard, StoryboardShot} from "@/lib/types";

export function sequence(shots:StoryboardShot[]):StoryboardShot[] {
  let start=0;
  return shots.map((shot)=>{const next={...shot,start_ms:start};start+=shot.duration_ms;return next;});
}

export function blankShot(duration_ms:number,id=crypto.randomUUID()):StoryboardShot {
  return {id,start_ms:0,duration_ms,beat:"",on_screen_text:"",visual_description:"",camera_intent:"Static",motion_intent:"Static",audio_cue:"",asset_ids:[],claim_ids:[]};
}

export function resizeShot(board:CreativeStoryboard,index:number,duration:number):CreativeStoryboard {
  if(index<0||index>=board.shots.length-1||!Number.isInteger(duration)||duration<1)return board;
  const next=board.shots.map((shot)=>({...shot}));const delta=duration-next[index].duration_ms;
  if(next[index+1].duration_ms-delta<1)return board;
  next[index].duration_ms=duration;next[index+1].duration_ms-=delta;
  return {...board,shots:sequence(next)};
}

export function splitShot(board:CreativeStoryboard,index:number,id=crypto.randomUUID()):CreativeStoryboard {
  if(index<0||index>=board.shots.length||board.shots.length>=100)return board;
  const next=[...board.shots];const first=Math.floor(next[index].duration_ms/2);
  if(first<1||next[index].duration_ms-first<1)return board;
  next[index]={...next[index],duration_ms:first};next.splice(index+1,0,blankShot(board.shots[index].duration_ms-first,id));
  return {...board,shots:sequence(next)};
}

export function removeShot(board:CreativeStoryboard,index:number):CreativeStoryboard {
  if(index<0||index>=board.shots.length||board.shots.length<2)return board;
  const next=board.shots.map((shot)=>({...shot}));const removed=next.splice(index,1)[0];
  next[Math.max(0,index-1)].duration_ms+=removed.duration_ms;
  return {...board,shots:sequence(next)};
}

export function moveShot(board:CreativeStoryboard,index:number,offset:-1|1):CreativeStoryboard {
  if(index<0||index+offset<0||index+offset>=board.shots.length)return board;
  const next=[...board.shots];[next[index],next[index+offset]]=[next[index+offset],next[index]];
  return {...board,shots:sequence(next)};
}

export function syncDuration(board:CreativeStoryboard,duration_ms:number,fps:CreativeStoryboard["fps"]):CreativeStoryboard {
  if(!Number.isInteger(duration_ms)||duration_ms<3000||duration_ms>600000)return board;
  const next=board.shots.map((shot)=>({...shot}));const delta=duration_ms-board.duration_ms;
  if(next.at(-1)!.duration_ms+delta<1)return board;
  next.at(-1)!.duration_ms+=delta;
  return {...board,duration_ms,fps,shots:sequence(next)};
}
