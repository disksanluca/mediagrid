import {describe,it,expect,vi} from "vitest";
import {renderToStaticMarkup} from "react-dom/server";
import {createElement} from "react";
import sports from "../../../../contracts/motion/recipes/sports.depth-impact.1.1.0.json";
import sports12 from "../../../../contracts/motion/recipes/sports.depth-impact.1.2.0.json";
import music12 from "../../../../contracts/motion/recipes/music.orbital-sleeve.1.2.0.json";
import geo12 from "../../../../contracts/motion/recipes/geo.route-explainer.1.2.0.json";
import type {MotionSceneSpec} from "../../../../contracts/motion/generated/motion-contracts";
import {animated,ease,frameAt,along,project,identity,particle} from "../../../renderer/src/motion-evaluate";
const playback=vi.hoisted(()=>({frame:30}));
vi.mock("remotion",()=>({
  staticFile:(file:string)=>file,
  useCurrentFrame:()=>playback.frame,
  useVideoConfig:()=>({width:1080,height:1920,fps:30}),
  AbsoluteFill:({children}: {children:unknown})=>children,
  Img:()=>null,OffthreadVideo:()=>null,Sequence:({children}: {children:unknown})=>children,
}));
import {MotionSceneRenderer} from "../../../renderer/src/motion-scene";
const graph=sports.scenes[0].graph as MotionSceneSpec["graph"];

describe("Shared motion evaluator",()=>{
  it.each([
    ["sports",sports12,"Barlow Condensed"],
    ["music",music12,"Space Grotesk"],
    ["geo",geo12,"IBM Plex Sans"],
  ] as const)("renders %s materials with the shared interpreter and no accumulated seek state",(_label,recipe,font)=>{
    const graph=recipe.scenes[0].graph as unknown as MotionSceneSpec["graph"];
    const texts=Object.fromEntries(graph.nodes.filter(n=>n.type==="text").map(n=>[n.id,"APPROVED"]));
    const item={id:"recipe-proof",start_ms:0,duration_ms:recipe.scenes[0].required_duration_ms,z_index:10,
      motion:{schema_version:"motion_scene_render_v1" as const,graph,
        palette:["#071217","#FFF4DA","#F4BE4E","#25423C","#78918A","#B76D28","#63BAC6"],
        fonts:[font,font] as MotionSceneSpec["fonts"],texts,assets:{},
        media_files:{cover:"cover.png",waveform:"wave.mp4",score:"score.wav"}}};
    const render=()=>renderToStaticMarkup(createElement(MotionSceneRenderer,{item}));
    playback.frame=30;const original=render();
    expect(original).toContain("Gradient");
    expect(original).toContain('data-motion-text');
    expect(original).not.toContain("NaN");
    playback.frame=75;expect(render()).not.toEqual(original);
    playback.frame=30;expect(render()).toEqual(original);
  });
  it("uses absolute quantization and holds endpoints",()=>{
    expect(frameAt(1001)+frameAt(10999)).toBe(360);
    const node={animations:[{property:"opacity" as const,keyframes:[
      {time:{kind:"ms" as const,at_ms:0},value:0},
      {time:{kind:"ms" as const,at_ms:1000},value:1}]}]};
    expect(animated(node,"opacity",1,-8,graph,1001)).toBe(0);
    expect(animated(node,"opacity",1,15,graph,1001)).toBe(.5);
    expect(animated(node,"opacity",1,90,graph,1001)).toBe(1);
  });
  it("solves cubic Bezier x, rather than treating time as its parameter",()=>{
    expect(ease(.5,{kind:"cubic_bezier",controls:[.16,1,.3,1]})).toBeGreaterThan(.9);
    expect(ease(.5,"hold")).toBe(0);
    expect(ease(1,"hold")).toBe(1);
  });
  it("projects far layers with less relative camera displacement",()=>{
    const near=project(identity,0,{position:[100,0,0]},0,graph,0,1080,1920);
    const far=project(identity,400,{position:[100,0,0]},0,graph,0,1080,1920);
    const nearBase=project(identity,0,{},0,graph,0,1080,1920);
    const farBase=project(identity,400,{},0,graph,0,1080,1920);
    expect(near[4]-nearBase[4]).toBeCloseTo(-100);
    expect(far[4]-farBase[4]).toBeCloseTo(-75);
  });
  it("travels by arc length and uses repeatable particle seeds",()=>{
    expect(along([[0,0],[30,0],[30,40]],.5)).toEqual([30,5]);
    expect(particle(4,8)).toEqual(particle(4,8));
    expect(particle(4,8)).not.toEqual(particle(4,9));
  });
  it("emits valid direct SVG clip shapes and reproduces nonsequential seeks",()=>{
    const item={id:"proof",start_ms:0,duration_ms:2000,z_index:10,motion:{
      schema_version:"motion_scene_render_v1" as const,graph,
      palette:["#101A21","#F4F0E6","#D7FF3F","#29434A"],
      fonts:["Barlow Condensed","Barlow Condensed"] as ["Barlow Condensed","Barlow Condensed"],
      texts:{headline:"ENTRE\nEM JOGO"},assets:{score:"original"},media_files:{score:"original.wav"},
    }};
    const render=()=>renderToStaticMarkup(createElement(MotionSceneRenderer,{item}));
    playback.frame=30;const first=render();
    expect(first).toMatch(/<clipPath[^>]*><rect/);
    expect(first).toContain("ENTRE");
    expect(first).not.toContain("NaN");
    playback.frame=48;expect(render()).not.toEqual(first);
    playback.frame=30;expect(render()).toEqual(first);
  });
});
