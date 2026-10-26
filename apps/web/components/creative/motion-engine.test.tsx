import {describe,it,expect,vi} from "vitest";
import {renderToStaticMarkup} from "react-dom/server";
import {createElement} from "react";
import sports from "../../../../contracts/motion/recipes/sports.depth-impact.1.1.0.json";
import type {MotionSceneSpec} from "../../../../contracts/motion/generated/motion-contracts";
import {animated,ease,frameAt,along,project,identity,particle} from "../../../renderer/src/motion-evaluate";
const playback=vi.hoisted(()=>({frame:30}));
vi.mock("remotion",()=>({
  useCurrentFrame:()=>playback.frame,
  useVideoConfig:()=>({width:1080,height:1920,fps:30}),
  AbsoluteFill:({children}: {children:unknown})=>children,
  Img:()=>null,OffthreadVideo:()=>null,Sequence:({children}: {children:unknown})=>children,
}));
import {MotionSceneRenderer} from "../../../renderer/src/motion-scene";
const graph=sports.scenes[0].graph as MotionSceneSpec["graph"];

describe("Shared motion evaluator",()=>{
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
