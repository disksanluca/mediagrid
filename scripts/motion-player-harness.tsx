// Test-only harness: mounts the production Player and EDL v2 composition.
import {createRoot} from "react-dom/client";
import {createRef} from "react";
import {Player, type PlayerRef} from "@remotion/player";
import {MediaGridTimelineV2} from "../apps/renderer/src/timeline-v2";

const nextPaint = () => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
const config = await fetch("/config.json").then(r => r.json());
const ref = createRef<PlayerRef>();
const scale = config.displayWidth / config.width;
createRoot(document.getElementById("root")!).render(<Player ref={ref}
  component={MediaGridTimelineV2} inputProps={config.props} compositionWidth={config.width}
  compositionHeight={config.height} durationInFrames={config.frames} fps={30}
  style={{width: config.displayWidth, height: config.height * scale}} controls={false}
  loop initiallyMuted />);
const sleep = (ms:number) => new Promise(resolve => setTimeout(resolve,ms));
while (!ref.current) await nextPaint();
await nextPaint();
await document.fonts.ready;
await Promise.all(Array.from(document.images).map(img => img.decode().catch(() => undefined)));
await sleep(150);

const qa = {
  ready: true,
  async seek(frame:number) {
    ref.current!.pause();
    ref.current!.seekTo(frame);
    await nextPaint();
    await document.fonts.ready;
    for(let i=0;i<100;i++) {
      if(Array.from(document.querySelectorAll("video")).every(v=>!v.seeking && v.readyState>=2)) break;
      await sleep(10);
    }
    await nextPaint();
    const actual=ref.current!.getCurrentFrame();
    if(actual!==frame) throw new Error("Player seek frame mismatch");
    const stage=document.getElementById("root")!.getBoundingClientRect();
    const overlay=config.props.overlays.find((o:any) => frame>=Math.round(o.start_ms*30/1000) &&
      frame<Math.round((o.start_ms+o.duration_ms)*30/1000));
    const safe=overlay.motion.graph.safe_area;
    const texts=Array.from(document.querySelectorAll<SVGTextElement>("[data-motion-text]")).map(el=>{
      const b=el.getBoundingClientRect();
      let opacity=1;
      for(let node:Element|null=el;node;node=node.parentElement) opacity*=Number(getComputedStyle(node).opacity);
      const bounds={x:(b.x-stage.x)/scale,y:(b.y-stage.y)/scale,width:b.width/scale,height:b.height/scale};
      return {id:el.dataset.motionText,text:el.textContent,opacity,bounds,
        safe:bounds.x>=safe.left-1 && bounds.y>=safe.top-1 &&
          bounds.x+bounds.width<=config.width-safe.right+1 &&
          bounds.y+bounds.height<=config.height-safe.bottom+1};
    });
    return {frame:actual,texts,videoTimes:Array.from(document.querySelectorAll("video")).map(v=>v.currentTime)};
  },
  async measure(milliseconds=10000) {
    const frames:{frame:number;ms:number}[]=[];
    const start=performance.now();
    const record=(e:any)=>frames.push({frame:e.detail.frame,ms:performance.now()-start});
    ref.current!.addEventListener("frameupdate",record);
    ref.current!.play();
    await sleep(milliseconds);
    ref.current!.pause();
    ref.current!.removeEventListener("frameupdate",record);
    const wall=performance.now()-start;
    return {wall_ms:wall,frame_events:frames.length,unique_frames_per_second:frames.length/(wall/1000),events:frames};
  }
};
(window as any).motionQA=qa;
