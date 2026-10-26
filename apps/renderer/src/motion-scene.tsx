import {Fragment, type ReactNode} from "react";
import {AbsoluteFill, Img, OffthreadVideo, Sequence, useCurrentFrame, useVideoConfig} from "remotion";
import type {MotionSceneSpec, ShapeNode} from "../../../contracts/motion/generated/motion-contracts";
import {animated, along, frameAt, identity, multiply, particle, point, project, transform, type Matrix, type Node} from "./motion-evaluate";
type Geometry=ShapeNode["params"]["geometry"];
import {mediaSource} from "./media-source";

export type MotionRenderData=MotionSceneSpec & {media_files:Record<string,string>};
export interface MotionOverlay {id:string;start_ms:number;duration_ms:number;z_index:number;motion:MotionRenderData}
const matrixString=(m:Matrix)=>`matrix(${m.join(" ")})`;
function geometry(g:Geometry,extra:Record<string,unknown>={}):ReactNode {
  if(g.kind==="rect")return <rect width={g.width} height={g.height} {...extra}/>;
  if(g.kind==="ellipse")return <ellipse cx={g.width/2} cy={g.height/2} rx={g.width/2} ry={g.height/2} {...extra}/>;
  if(!("points" in g))throw new Error("Unsupported geometry");
  const points=g.points.map(p=>p.join(",")).join(" ");
  return g.kind==="polygon"?<polygon points={points} {...extra}/>:<polyline points={points} {...extra}/>;
}
function bounds(g:Geometry):number[] {
  return "width" in g?[g.width,g.height]:[
    Math.max(...g.points.map(p=>p[0]))-Math.min(0,...g.points.map(p=>p[0])),
    Math.max(...g.points.map(p=>p[1]))-Math.min(0,...g.points.map(p=>p[1]))];
}
export function MotionSceneRenderer({item}:{item:MotionOverlay}) {
  const frame=useCurrentFrame();
  const {width,height}=useVideoConfig();
  const spec=item.motion,scene=spec.graph;
  const nodes=new Map(scene.nodes.map(n=>[n.id,n]));
  const palette=(index:number)=>{const color=spec.palette[index];if(!color)throw new Error("Missing DNA color");return color;};
  const sample=(n:Node,property:string,base:number)=>animated(n,property,base,frame,scene,item.start_ms);
  type State={matrix:Matrix;z:number;opacity:number;active:[number,number];order:number[];masks:Node[]};
  const states=new Map<string,State>();
  const state=(n:Node):State=>{
    const cached=states.get(n.id);if(cached)return cached;
    const parent=n.parent_id?state(nodes.get(n.parent_id)!):
      {matrix:identity,z:0,opacity:1,active:[0,item.duration_ms] as [number,number],order:[],masks:[]};
    const local=transform(n,frame,scene,item.start_ms);
    const ownMask=scene.nodes.find(m=>m.type==="mask"&&m.params.target_id===n.id);
    const result={matrix:multiply(parent.matrix,local.matrix),z:parent.z+local.z,
      opacity:parent.opacity*local.opacity,active:(n.active_ms??parent.active) as [number,number],
      order:[...parent.order,n.z_index??0,scene.nodes.indexOf(n)],
      masks:ownMask?[...parent.masks,ownMask]:parent.masks};
    states.set(n.id,result);return result;
  };
  const visible=(s:State)=>frame>=frameAt(item.start_ms+s.active[0])-frameAt(item.start_ms)&&
    frame<frameAt(item.start_ms+s.active[1])-frameAt(item.start_ms);
  const projected=(n:Node,m?:Matrix)=>{
    const s=state(n),matrix=m??s.matrix;
    return n.space==="screen"?matrix:project(matrix,s.z,scene.camera??{},frame,scene,item.start_ms,width,height);
  };
  const leaves=scene.nodes.filter(n=>n.type!=="group"&&n.type!=="mask").sort((a,b)=>{
    const aa=state(a).order,bb=state(b).order;
    for(let i=0;i<Math.max(aa.length,bb.length);i++){const d=(aa[i]??0)-(bb[i]??0);if(d)return d;}
    return 0;
  });
  const render=(n:Node)=>{
    const s=state(n);if(!visible(s))return null;
    let content:ReactNode=null,size=[0,0],matrix=s.matrix;
    if(n.type==="text"){
      const p=n.params,text=spec.texts[n.id];
      size=[p.max_width,p.size*(p.line_height??1)*(text?.split("\n").length??1)];
      content=<text fill={palette(p.fill.index)} fontFamily="MG Barlow" fontWeight={700}
        fontSize={p.size} style={{fontKerning:"none",fontVariantLigatures:"none"}}
        textAnchor={p.align==="center"?"middle":p.align==="right"?"end":"start"}>
        {text.split("\n").map((line,i)=><tspan key={i} x={p.align==="center"?p.max_width/2:p.align==="right"?p.max_width:0}
          y={p.size*.84+i*p.size*(p.line_height??1)}>{line}</tspan>)}
      </text>;
    }else if(n.type==="shape"){
      const p=n.params,progress=sample(n,"draw_progress",p.draw_progress??1);size=bounds(p.geometry);
      content=geometry(p.geometry,{fill:p.fill?palette(p.fill.index):"none",fillOpacity:progress,
        stroke:p.stroke?palette(p.stroke.index):"none",strokeWidth:p.stroke_width??1,
        strokeLinejoin:"round",strokeLinecap:"round",pathLength:1,
        strokeDasharray:1,strokeDashoffset:1-progress});
    }else if(n.type==="path_follower"){
      const path=nodes.get(n.params.path_ref);
      if(!path||path.type!=="shape"||!("points" in path.params.geometry))throw new Error("Invalid path");
      const progress=sample(n,"progress",n.params.progress??0);
      const p=point(transform(path,frame,scene,item.start_ms).matrix,along(path.params.geometry.points,progress));
      const parent=n.parent_id?state(nodes.get(n.parent_id)!):{matrix:identity};
      const local=transform(n,frame,scene,item.start_ms).matrix;
      local[4]+=p[0];local[5]+=p[1];matrix=multiply(parent.matrix,local);
      size=[n.params.marker.width,n.params.marker.height];
      content=geometry(n.params.marker,{fill:palette(n.params.fill.index)});
    }else if(n.type==="image"||n.type==="video"){
      const p=n.params,source=spec.media_files[p.asset_binding];
      if(!source)throw new Error("Unstaged motion asset");
      size=[p.width,p.height];
      const style={width:p.width,height:p.height,objectFit:p.fit??"contain" as const};
      content=<foreignObject width={p.width} height={p.height} overflow="hidden">
        {n.type==="image"?<Img src={mediaSource(source)} style={style}/>:<Sequence layout="none"
          from={frameAt(item.start_ms+s.active[0])-frameAt(item.start_ms)}
          durationInFrames={frameAt(item.start_ms+s.active[1])-frameAt(item.start_ms+s.active[0])}>
          <OffthreadVideo muted src={mediaSource(source)} trimBefore={frameAt(n.params.source_in_ms??0)} style={style}/>
        </Sequence>}
      </foreignObject>;
    }else if(n.type==="particle"){
      const p=n.params,elapsed=(frame+frameAt(item.start_ms))*1000/30-item.start_ms-s.active[0];
      content=<g fill={palette(p.fill.index)}>{Array.from({length:p.count},(_,i)=>{
        const phase=particle(p.seed,i),life=elapsed/1000;
        return <circle key={i} cx={(phase-.5)*width+p.velocity[0]*life}
          cy={(particle(p.seed+1,i)-.5)*height+p.velocity[1]*life}
          r={p.radius*(.35+.65*phase)} opacity={.2+.6*phase}/>;
      })}</g>;
    }else if(n.type==="light_sweep"){
      const p=n.params,id=`sweep-${item.id}-${n.id}`;size=[p.width,height*2];
      content=<g transform={`rotate(${p.angle??0})`} opacity={p.intensity??.5}>
        <defs><linearGradient id={id}><stop offset="0" stopColor={palette(p.fill.index)} stopOpacity="0"/>
          <stop offset=".5" stopColor={palette(p.fill.index)}/><stop offset="1" stopColor={palette(p.fill.index)} stopOpacity="0"/>
        </linearGradient><filter id={id+"-blur"} x="-50%" y="-20%" width="200%" height="140%">
          <feGaussianBlur stdDeviation={p.blur??0}/></filter></defs>
        <rect width={size[0]} height={size[1]} fill={`url(#${id})`} filter={p.blur?`url(#${id}-blur)`:undefined}/>
      </g>;
    }
    const anchor=n.anchor??[0,0];
    matrix=multiply(matrix,[1,0,0,1,-anchor[0]*size[0],-anchor[1]*size[1]]);
    let result=<g transform={matrixString(projected(n,matrix))} opacity={s.opacity}>{content}</g>;
    for(const mask of s.masks)result=<g clipPath={`url(#clip-${item.id}-${mask.id})`}>{result}</g>;
    return <Fragment key={n.id}>{result}</Fragment>;
  };
  return <AbsoluteFill style={{zIndex:item.z_index,pointerEvents:"none"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{overflow:"hidden"}}>
      <rect width={width} height={height} fill={palette(0)}/>
      <defs>{scene.nodes.filter(n=>n.type==="mask").map(n=>{
        if(n.type!=="mask")return null;
        const progress=visible(state(n))?sample(n,"progress",n.params.progress??1)*state(n).opacity:0;
        const size=bounds(n.params.geometry),anchor=n.anchor??[0,0];
        const anchored=multiply(projected(n),[1,0,0,1,-anchor[0]*size[0],-anchor[1]*size[1]]);
        const matrix=multiply(anchored,[progress,0,0,1,0,0]);
        return <clipPath key={n.id} id={`clip-${item.id}-${n.id}`} clipPathUnits="userSpaceOnUse">
          {geometry(n.params.geometry,{transform:matrixString(matrix)})}
        </clipPath>;
      })}</defs>
      {leaves.map(render)}
      {spec.diagnostics&&<><rect x={scene.safe_area?.left??72} y={scene.safe_area?.top??120}
        width={width-(scene.safe_area?.left??72)-(scene.safe_area?.right??72)}
        height={height-(scene.safe_area?.top??120)-(scene.safe_area?.bottom??180)}
        fill="none" stroke="#ff00ff" strokeWidth={2}/>
        <text x={24} y={40} fill="#ff00ff" fontSize={24}>M4 / FRAME {frame} / {scene.nodes.length} NODES</text></>}
    </svg>
  </AbsoluteFill>;
}
