import type {Camera, MotionScene} from "../../../contracts/motion/generated/motion-contracts";
export type Node=MotionScene["nodes"][number];
type Animation=NonNullable<Node["animations"]>[number];
type TimeRef=Animation["keyframes"][number]["time"];
type Easing=NonNullable<Animation["keyframes"][number]["easing"]>;

export const frameAt = (ms:number) => Math.floor((ms*30+500)/1000);
export const clamp = (v:number) => Math.max(0,Math.min(1,v));
export function ease(t:number, curve:Easing = "linear"):number {
  t=clamp(t);
  if(curve==="hold")return t===1?1:0;
  if(curve==="cubic_out")return 1-(1-t)**3;
  if(curve==="cubic_in_out")return t<.5?4*t*t*t:1-(-2*t+2)**3/2;
  if(typeof curve==="string")return t;
  const [x1,y1,x2,y2]=curve.controls;
  const cubic=(p:number,a:number,b:number)=>3*(1-p)**2*p*a+3*(1-p)*p*p*b+p*p*p;
  let low=0,high=1;
  for(let i=0;i<28;i++){const mid=(low+high)/2;if(cubic(mid,x1,x2)<t)low=mid;else high=mid;}
  return cubic((low+high)/2,y1,y2);
}
export function resolveTime(time:TimeRef,scene:MotionScene):number {
  if(time.kind==="ms")return time.at_ms;
  const cue=scene.cues?.find((c)=>c.id===time.cue_ref);
  if(!cue)throw new Error("Missing motion cue");
  return cue.at_ms+(time.offset_ms??0);
}
type Animated = {animations?:Animation[]};
export function animated<T extends number|number[]>(node:Animated,property:string,base:T,
  frame:number,scene:MotionScene,startMs:number):T {
  const animation=node.animations?.find((a)=>a.property===property);
  if(!animation)return base;
  const keys=animation.keyframes;
  const times=keys.map(k=>frameAt(startMs+resolveTime(k.time,scene))-frameAt(startMs));
  if(frame<=times[0])return keys[0].value as T;
  if(frame>=times[times.length-1])return keys[keys.length-1].value as T;
  let i=0;while(frame>times[i+1])i++;
  const t=ease((frame-times[i])/(times[i+1]-times[i]),keys[i].easing);
  const a=keys[i].value,b=keys[i+1].value;
  return (Array.isArray(a)&&Array.isArray(b)?a.map((v,j)=>v+(b[j]-v)*t):
    (a as number)+((b as number)-(a as number))*t) as T;
}
export type Matrix=[number,number,number,number,number,number];
export const identity:Matrix=[1,0,0,1,0,0];
export function multiply(a:Matrix,b:Matrix):Matrix {
  return [a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],
    a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],
    a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]];
}
export const point=(m:Matrix,p:number[])=>[m[0]*p[0]+m[2]*p[1]+m[4],m[1]*p[0]+m[3]*p[1]+m[5]];
export function along(points:number[][],progress:number):number[] {
  const lengths=points.slice(1).map((p,i)=>Math.hypot(p[0]-points[i][0],p[1]-points[i][1]));
  let remaining=clamp(progress)*lengths.reduce((a,b)=>a+b,0);
  for(let i=0;i<lengths.length;i++){
    if(remaining<=lengths[i]||i===lengths.length-1){
      const t=lengths[i]?remaining/lengths[i]:0;
      return [points[i][0]+(points[i+1][0]-points[i][0])*t,points[i][1]+(points[i+1][1]-points[i][1])*t];
    }
    remaining-=lengths[i];
  }
  return points[0];
}
export function transform(node:Node,frame:number,scene:MotionScene,start:number) {
  const position=animated(node,"position",node.position??[0,0,0],frame,scene,start);
  const scale=animated(node,"scale",node.scale??[1,1],frame,scene,start);
  const angle=animated(node,"rotate_z",node.rotate_z??0,frame,scene,start)*Math.PI/180;
  return {matrix:[Math.cos(angle)*scale[0],Math.sin(angle)*scale[0],
    -Math.sin(angle)*scale[1],Math.cos(angle)*scale[1],position[0],position[1]] as Matrix,
    z:position[2],opacity:animated(node,"opacity",node.opacity??1,frame,scene,start)};
}
export function project(matrix:Matrix,z:number,camera:Camera,frame:number,scene:MotionScene,
  start:number,width:number,height:number):Matrix {
  const position=animated(camera,"position",camera.position??[0,0,0],frame,scene,start);
  const angle=-animated(camera,"rotate_z",camera.rotate_z??0,frame,scene,start)*Math.PI/180;
  const focal=camera.focal_length??1200;
  const p=focal/(focal+z-position[2]);
  const c=Math.cos(angle)*p,s=Math.sin(angle)*p;
  const view:Matrix=[c,s,-s,c,width/2-c*(width/2+position[0])+s*(height/2+position[1]),
    height/2-s*(width/2+position[0])-c*(height/2+position[1])];
  return multiply(view,matrix);
}
export function particle(seed:number,index:number):number {
  let x=(seed^Math.imul(index+1,0x45d9f3b))>>>0;
  x=Math.imul(x^(x>>>16),0x45d9f3b)>>>0;
  return ((x^(x>>>16))>>>0)/4294967296;
}
