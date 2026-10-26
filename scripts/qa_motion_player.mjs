/**
 * Disposable headless QA using Remotion's installed browser API.
 * Never controls a user's browser/profile. Only serves a fixed proof-file allowlist on loopback.
 * Usage: node scripts/qa_motion_player.mjs data/m4-complete-proof/RUN [sports music geo]
 */
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import {execFileSync,spawn} from "node:child_process";
import {performance} from "node:perf_hooks";
import {build} from "esbuild";
import {openBrowser} from "@remotion/renderer";

const root=process.cwd(),base=path.resolve(root,"data/m4-complete-proof"),run=path.resolve(process.argv[2]||"");
if(!run.startsWith(base+path.sep)) throw new Error("Only disposable M4 proof directories allowed");
const labels=process.argv.slice(3).length?process.argv.slice(3):["sports","music","geo"];
const digest=b=>crypto.createHash("sha256").update(b).digest("hex");
const output=await build({entryPoints:["scripts/motion-player-harness.tsx"],bundle:true,write:false,
  format:"esm",jsx:"automatic",define:{"process.env.NODE_ENV":'"production"'}});
for(const label of labels) {
  if(!["sports","music","geo"].includes(label)) throw new Error("Unknown proof");
  const folder=path.join(run,label),out=path.join(folder,"player-qa");
  fs.mkdirSync(out,{recursive:true});
  const input=JSON.parse(fs.readFileSync(path.join(folder,"preview.json"),"utf8"));
  const {width,height,frames}=input.plan.render;
  const displayWidth=width/2;
  const mediaNames={score:"score.wav",cover:"orbita-original.png",waveform:"original-waveform.mp4"};
  const files=new Map();
  for(const asset of input.plan.assets) {
    const file=path.join(folder,mediaNames[asset.slot]);
    const bytes=fs.readFileSync(file);
    if(digest(bytes)!==asset.sha256) throw new Error("Proof asset SHA mismatch");
    files.set("/media/"+asset.id,{bytes,type:{audio:"audio/wav",image:"image/png",video:"video/mp4"}[asset.metadata.kind]});
  }
  let config;
  const server=http.createServer((req,res)=>{
    if(req.url==="/") {res.setHeader("Content-Type","text/html");res.end('<!doctype html><style>html,body{margin:0;background:#000}#root{display:inline-block}</style><div id="root"></div><script type="module" src="/harness.js"></script>');}
    else if(req.url==="/harness.js"){res.setHeader("Content-Type","application/javascript");res.end(output.outputFiles[0].contents);}
    else if(req.url==="/config.json"){res.setHeader("Content-Type","application/json");res.end(JSON.stringify(config));}
    else if(files.has(req.url)){
      const file=files.get(req.url),range=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
      res.setHeader("Content-Type",file.type);res.setHeader("Accept-Ranges","bytes");
      if(range){const start=Number(range[1]),end=Math.min(Number(range[2]||file.bytes.length-1),file.bytes.length-1);
        if(start>end){res.writeHead(416).end();return;}
        res.writeHead(206,{"Content-Range":`bytes ${start}-${end}/${file.bytes.length}`,"Content-Length":end-start+1});
        res.end(file.bytes.subarray(start,end+1));
      }else {res.setHeader("Content-Length",file.bytes.length);res.end(file.bytes);}
    }else res.writeHead(404).end();
  });
  await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
  const origin="http://127.0.0.1:"+server.address().port;
  const props=structuredClone(input.props);
  props.sounds.forEach(s=>s.media_file=origin+"/media/"+s.source_asset_id);
  props.overlays.forEach(o=>{
    if(o.preset==="motion_scene_v1") Object.keys(o.motion.assets).forEach(slot=>o.motion.media_files[slot]=origin+"/media/"+o.motion.assets[slot]);
  });
  config={props,width,height,frames,displayWidth};
  let browser;
  const started=performance.now();
  try {
    browser=await openBrowser("chrome",{logLevel:"error"});
    const page=await browser.newPage({context:()=>null,logLevel:"error",indent:false,pageIndex:0,
      onBrowserLog:log=>{if(log.type==="error") console.error(log.text);},onLog:()=>{}});
    await page.setViewport({width:displayWidth,height:height/2,deviceScaleFactor:1});
    await page.goto({url:origin,timeout:30000});
    for(let i=0;i<200;i++){
      if(await page.evaluate(()=>Boolean(window.motionQA?.ready)))break;
      await new Promise(r=>setTimeout(r,50));
    }
    if(!await page.evaluate(()=>Boolean(window.motionQA?.ready)))throw new Error("Player did not become ready");
    const coldStart=(performance.now()-started)/1000;
    const ordered=[...new Set(props.overlays.flatMap(o=>{
      const start=Math.round(o.start_ms*.03),end=Math.round((o.start_ms+o.duration_ms)*.03);
      return [start+Math.min(30,end-start-1),Math.round((start+end)/2),end-1];
    }))].sort((a,b)=>a-b);
    const captures=new Map(),svgHashes=new Map(),safeChecks=[];
    async function capture(frame) {
      const state=await page.evaluate(f=>window.motionQA.seek(f),frame);
      safeChecks.push(state);
      const svg=await page.evaluate(()=>Array.from(document.querySelectorAll("svg")).map(s=>s.outerHTML).join(""));
      state.svg_sha256=digest(Buffer.from(svg));
      // Wait for the compositor too: first SVG filter paint can lag the DOM's frame.
      // Require two stable captures without advancing the Player; never modify the recipe.
      let previous=null;
      for(let attempt=0;attempt<8;attempt++){
        const screenshot=await page._client().send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});
        const bytes=Buffer.from(screenshot.value.data,"base64");
        if(previous&&digest(bytes)===digest(previous))return bytes;
        previous=bytes;
        await new Promise(r=>setTimeout(r,80));
      }
      throw new Error("Player compositor did not stabilize at frame "+frame);
    }
    for(const f of ordered) {
      const png=await capture(f);captures.set(f,png);svgHashes.set(f,safeChecks.at(-1).svg_sha256);
      fs.writeFileSync(path.join(out,`player-${f}.png`),png);
    }
    const seekChecks=[];
    for(const f of [...ordered].reverse()) {
      const png=await capture(f);
      fs.writeFileSync(path.join(out,`seek-${f}.png`),png);
      const equal=digest(png)===digest(captures.get(f));
      let maxDelta=0,changed=0,sumDelta=0,total=displayWidth*height/2*3;
      if(!equal){
        const raw=prefix=>execFileSync("ffmpeg",["-v","error","-i",path.join(out,`${prefix}-${f}.png`),
          "-f","rawvideo","-pix_fmt","rgb24","-"],{maxBuffer:20*1024*1024});
        const a=raw("player"),b=raw("seek");total=a.length;
        for(let i=0;i<a.length;i++){const delta=Math.abs(a[i]-b[i]);sumDelta+=delta;maxDelta=Math.max(maxDelta,delta);if(delta)changed++;}
      }
      const sameSvg=svgHashes.get(f)===safeChecks.at(-1).svg_sha256;
      seekChecks.push({frame:f,identical_png:equal,identical_svg:sameSvg,max_channel_delta:maxDelta,
        mean_channel_delta:sumDelta/total,changed_channel_fraction:changed/total,
        passed:sameSvg&&maxDelta<=2&&sumDelta/total<=.2});
    }
    // Exhaustive typography geometry over all 1110 delivered frames across three proofs.
    for(let f=0;f<frames;f++){
      const state=await page.evaluate(n=>window.motionQA.seek(n),f);
      if(state.texts.some(t=>t.opacity>.98&&!t.safe))safeChecks.push(state);
    }
    const overflow=safeChecks.flatMap(s=>s.texts.filter(t=>t.opacity>.98&&!t.safe).map(t=>({frame:s.frame,...t})));
    await page.evaluate(()=>window.motionQA.seek(0));
    const stop=path.join(out,"preview.stop"),perfFile=path.join(out,"performance.json");
    if(fs.existsSync(stop))fs.unlinkSync(stop);
    const sampler=process.platform==="win32"?spawn("powershell",["-NoProfile","-File",
      path.join(root,"scripts/measure-motion-process.ps1"),"-RootProcessId",String(process.pid),
      "-StopPath",stop,"-OutputPath",perfFile],{windowsHide:true,stdio:"ignore"}):null;
    const samplerDone=sampler?new Promise((resolve,reject)=>{
      sampler.once("error",reject);sampler.once("exit",code=>code===0?resolve():reject(new Error("Preview sampler failed")));
    }):null;
    let preview;
    try {
      await page.evaluate(()=>window.motionQA.measure(1500));
      preview=await page.evaluate(()=>window.motionQA.measure(10000));
    }finally{
      if(sampler){fs.writeFileSync(stop,"stop");await samplerDone;fs.unlinkSync(stop);}
    }
    if(sampler)preview.process_tree=JSON.parse(fs.readFileSync(perfFile,"utf8").replace(/^\uFEFF/,""));
    const parity=[];
    for(const f of ordered){
      const exported=path.join(out,`export-${f}.png`),player=path.join(out,`player-${f}.png`);
      execFileSync("ffmpeg",["-v","error","-y","-i",path.join(folder,label+"-motion.mp4"),
        "-vf",`select=eq(n\\,${f}),scale=${width/2}:${height/2}:flags=lanczos`,"-frames:v","1",exported]);
      // FFmpeg writes filter statistics to stderr even on success.
      const measurement=await new Promise((resolve,reject)=>{
        import("node:child_process").then(({execFile})=>execFile("ffmpeg",["-hide_banner","-i",player,"-i",exported,
          "-lavfi","ssim","-f","null","-"],(err,stdout,stderr)=>err?reject(err):resolve(stderr)));
      });
      const ssim=Number(measurement.match(/All:([\d.]+)/)?.[1]);
      parity.push({frame:f,ssim,passed:ssim>=.96});
    }
    const report={label,composition:"MediaGridTimelineV2",player:"@remotion/player",scale:.5,
      fresh_browser_to_ready_seconds:coldStart,preview,ordered_frames:ordered,seek_checks:seekChecks,
      overflow,parity,thresholds:{ssim:.96,preview_fps:24,seek_max_8bit_channel_delta:2,seek_mean_channel_delta:.2},
      caveats:["Fresh headless browser; OS/filesystem/bundler caches may be warm.",
        "SSIM compares browser PNG with H264/BT709 decoded and Lanczos-scaled PNG; compression and video decoding may differ.",
        "Seeking requires identical SVG state. Chromium gradient dithering can vary by <=2/255; mean channel error must be <=0.2/255.",
        "Typography bounds checked every frame at opacity >0.98; intentional reveal masks are excluded from overflow definition.",
        "Measured headless Chromium; not an artistic approval or a benchmark of all user GPUs."]};
    fs.writeFileSync(path.join(out,"report.json"),JSON.stringify(report,null,2));
    console.log(JSON.stringify({label,cold_start:coldStart,preview_fps:preview.unique_frames_per_second,
      min_ssim:Math.min(...parity.map(p=>p.ssim)),seek_pass:seekChecks.every(s=>s.passed),overflows:overflow.length}));
    if(overflow.length||seekChecks.some(s=>!s.passed)||parity.some(p=>!p.passed)) throw new Error("Player QA failed; see report");
  }finally{
    if(browser)await browser.close({silent:true});
    await new Promise(resolve=>server.close(resolve));
  }
}
