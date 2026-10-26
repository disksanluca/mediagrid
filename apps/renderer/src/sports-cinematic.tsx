import {useEffect, useState} from "react";
import {AbsoluteFill, cancelRender, continueRender, delayRender, Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import type {RenderOverlay} from "./types";
import {sportsFontData} from "./sports-font";

const ease = Easing.bezier(.16, 1, .3, 1);
const clamp = {extrapolateLeft: "clamp" as const, extrapolateRight: "clamp" as const};
const ramp = (frame: number, a: number, b: number, x = 0, y = 1) =>
  interpolate(frame, [a, b], [x, y], {...clamp, easing: ease});

export function SportsFont() {
  const [handle] = useState(() => delayRender("Loading bundled OFL sports typography"));
  useEffect(() => {
    const face = new FontFace("MG Barlow", `url(${sportsFontData})`, {weight: "700"});
    void face.load().then((font) => {document.fonts.add(font); continueRender(handle);})
      .catch((error: unknown) => cancelRender(error instanceof Error ? error : new Error(String(error))));
  }, [handle]);
  return null;
}

// Original vector geometry: no club marks, players, footage or third-party imagery.
function Ball({x, y, radius, turn, accent}: {x:number;y:number;radius:number;turn:number;accent:string}) {
  return <g transform={`translate(${x} ${y}) scale(${radius / 240}) rotate(${turn})`}>
    <defs><radialGradient id="mg-ball" cx="30%" cy="25%" r="80%">
      <stop offset="0" stopColor="#fffef5"/><stop offset=".45" stopColor="#d9e1d7"/>
      <stop offset=".8" stopColor="#82928b"/><stop offset="1" stopColor="#253f37"/>
    </radialGradient><clipPath id="mg-ball-clip"><circle r="240"/></clipPath></defs>
    <circle r="254" fill="none" stroke={accent} strokeOpacity=".3" strokeWidth="2"/>
    <circle r="240" fill="url(#mg-ball)"/>
    <g clipPath="url(#mg-ball-clip)" stroke="#20342e" strokeWidth="5">
      <path d="M-70 -65 L42 -92 L112 4 L46 105 L-66 80 Z" fill="#132921"/>
      <path d="M-70 -65 L-132 -171 M42 -92 L85 -224 M112 4 L225 -4 M46 105 L101 222 M-66 80 L-175 180" fill="none"/>
      <path d="M-132 -171 L-90 -242 L-207 -195 L-237 -100 Z M85 -224 L151 -244 L235 -135 L206 -90 Z M225 -4 L280 60 L220 158 L165 124 Z M101 222 L53 280 L-60 235 L-45 177 Z M-175 180 L-267 143 L-237 35 L-189 40 Z" fill="#182e26"/>
      <path d="M-132 -171 L85 -224 M206 -90 L225 -4 M165 124 L101 222 M-45 177 L-175 180 M-189 40 L-237 -100" fill="none" strokeOpacity=".65"/>
    </g>
    <ellipse cx="-68" cy="-124" rx="100" ry="39" fill="#fff" opacity=".12" transform="rotate(-28)"/>
  </g>;
}

export function SportsCinematic({item}: {item:RenderOverlay}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const frames = Math.round(item.duration_ms * fps / 1000);
  const globalFrame = frame + Math.round(item.start_ms * fps / 1000);
  const points = item.keyframes.map((key) => key.at_ms * fps / 1000);
  const value = (key: "x" | "y" | "scale" | "opacity") => interpolate(
    frame, points, item.keyframes.map((point) => point[key]), {...clamp, easing: ease});
  const accent = item.color;
  const paper = item.paper ?? "#F4F0E6";
  const background = item.background ?? "#0B1013";
  const phase = item.phase ?? "impact";
  const enter = ramp(frame, 0, 16);
  const reveal = ramp(frame, 2, 17);
  const pulse = Math.exp(-(frame % 15) / 4);
  const exit = ramp(frame, frames - 8, frames);
  const drift = frame / Math.max(1, frames - 1);
  const titleY = phase === "impact" ? 700 : phase === "reveal" ? 1130 : phase === "play" ? 390 : 850;
  const titleSize = phase === "impact" ? 238 : phase === "resolve" ? 210 : 184;
  const longest = Math.max(...item.text.split("\n").map((line) => line.length));
  const fontSize = Math.min(titleSize, 1390 / Math.max(1, longest));
  return <AbsoluteFill style={{background, color:paper, overflow:"hidden", zIndex:item.z_index,
    fontFamily:'"MG Barlow", sans-serif', fontWeight:700}}>
    <svg viewBox="0 0 1080 1920" style={{position:"absolute",width:"100%",height:"100%"}}>
      <defs><radialGradient id="mg-atmosphere"><stop stopColor={accent} stopOpacity=".13"/>
        <stop offset="1" stopColor={background} stopOpacity="0"/></radialGradient>
        <pattern id="mg-grid" width="120" height="120" patternUnits="userSpaceOnUse"
          patternTransform={`translate(0 ${globalFrame * .35})`}>
          <path d="M120 0H0V120" fill="none" stroke={paper} strokeOpacity=".055" strokeWidth="1"/>
        </pattern></defs>
      <rect width="1080" height="1920" fill="url(#mg-grid)"/>
      <ellipse cx={670 + Math.sin(globalFrame / 60) * 140} cy="870" rx="830" ry="1000" fill="url(#mg-atmosphere)"/>
      {Array.from({length:36}, (_, i) => <circle key={i} cx={(i * 293 + globalFrame * (i % 3 + 1) * .3) % 1080}
        cy={(i * 487 + globalFrame * .2) % 1920} r={i % 3 === 0 ? 2 : 1} fill={paper} opacity=".16"/>)}
      <path d="M86 225V1695H940" fill="none" stroke={paper} strokeOpacity=".14"/>
      <path d="M87 225H265 M940 1695V1518" fill="none" stroke={accent} strokeWidth="3"/>
      {phase === "impact" && <>
        <g transform={`translate(540 1000) rotate(${-24 + drift * 15}) scale(${.8 + enter * .2})`}>
          {[340,430,520].map((r,i)=><ellipse key={r} rx={r} ry={r*.72} fill="none" stroke={accent}
            strokeWidth={i===1?3:1} opacity={.1 + i*.06} strokeDasharray={i===1?"180 120":"none"}/>)}
        </g>
        <path d={`M-100 ${1420 - drift * 130} L1180 ${950 - drift * 130}`} stroke={accent} strokeWidth="65" opacity=".9"/>
        <path d={`M-100 ${1520 - drift * 130} L1180 ${1050 - drift * 130}`} stroke={paper} strokeWidth="2" opacity=".5"/>
        <circle cx="870" cy="395" r={35 + pulse * 5} fill={accent}/>
      </>}
      {phase === "reveal" && <>
        <g transform={`translate(560 835) rotate(${-22 + drift * 30})`}>
          <ellipse rx="465" ry="180" fill="none" stroke={accent} strokeWidth="3" strokeDasharray="500 100"/>
          <ellipse rx="340" ry="430" fill="none" stroke={paper} strokeOpacity=".17"/>
          <path d="M-460 0H460 M0 -450V450" stroke={paper} strokeOpacity=".14" strokeDasharray="7 15"/>
        </g>
        <Ball x={610 - drift*80} y={880 - enter*90 - drift*60}
          radius={220 + enter*55 + drift*25} turn={-30 + frame*.38} accent={accent}/>
        <path d={`M90 530H${90 + enter*220}`} stroke={accent} strokeWidth="7"/>
      </>}
      {phase === "play" && <>
        <g transform={`translate(540 1070) rotate(${-17 + drift*9}) scale(${.95 + drift*.05})`}>
          <rect x="-360" y="-430" width="720" height="850" rx="5" fill="#17271f" stroke={paper} strokeOpacity=".5" strokeWidth="3"/>
          <path d="M-360 0H360 M-170 -430V-280H170V-430 M-170 420V270H170V420" fill="none" stroke={paper} strokeOpacity=".4" strokeWidth="3"/>
          <circle r="110" fill="none" stroke={paper} strokeOpacity=".4" strokeWidth="3"/>
          <path d="M-210 270Q200 150 -90 -10T210 -280" fill="none" stroke={accent} strokeWidth="9"
            strokeDasharray="1250" strokeDashoffset={1250*(1-ramp(frame,5,95))}/>
          {[[-210,270],[-90,-10],[210,-280]].map(([x,y],index)=><g key={index} opacity={ramp(frame,index*22,index*22+12)}>
            <circle cx={x} cy={y} r={35+pulse*6} fill={background} stroke={accent} strokeWidth="4"/>
            <text x={x} y={y+12} textAnchor="middle" fill={paper} fontSize="34">{String(index+1).padStart(2,"0")}</text>
          </g>)}
          <circle cx={interpolate(frame,[0,40,80,119],[-210,-90,70,210],clamp)}
            cy={interpolate(frame,[0,40,80,119],[270,-10,-120,-280],clamp)}
            r="13" fill={paper}/>
        </g>
        <path d="M935 660V1340" stroke={accent} strokeWidth="2" strokeDasharray="2 16"/>
      </>}
      {phase === "resolve" && <>
        <g transform={`translate(540 960) rotate(${frame*.4})`}>
          <circle r={320 + enter*140 + drift*40} fill="none" stroke={accent} strokeWidth={2 + (1-enter)*18}/>
          <circle r={480 + enter*65} fill="none" stroke={paper} opacity=".14" strokeDasharray="10 24"/>
        </g>
        <Ball x={800 - enter*190} y={420 - drift*35} radius={116 + drift*12}
          turn={frame*.6} accent={accent}/>
        <path d={`M${540-enter*240} 1240H${540+enter*240}`} stroke={accent} strokeWidth="9"/>
      </>}
    </svg>
    {item.diagnostics && <div style={{position:"absolute",left:108,right:120,top:250,display:"flex",justifyContent:"space-between",
      letterSpacing:4,fontSize:26,color:paper}}><span>MEDIAGRID / MOTION LAB</span><span style={{color:accent}}>VOL. 01</span></div>}
    <div style={{position:"absolute",left:`${value("x")*100}%`,top:titleY + (value("y")-.5)*1920,
      width:840,textAlign:phase==="resolve"?"center":"left",opacity:value("opacity"),
      transform:`translateX(-50%) translateY(${(1-enter)*100}px) scale(${value("scale")})`,
      clipPath:`inset(0 0 ${(1-reveal)*100}% 0)`}}>
      <div style={{fontSize:26,letterSpacing:6,color:accent,marginBottom:24}}>
        {phase==="impact"?"O INSTANTE ANTES":phase==="reveal"?"ENERGIA EM MOVIMENTO":phase==="play"?"CRIE O PRÓXIMO LANCE":"SEU MOVIMENTO COMEÇA"}
      </div>
      <div style={{fontSize,lineHeight:.88,letterSpacing:-2,whiteSpace:"pre-line",
        transform:"skewX(-5deg)",textShadow:`0 4px 30px ${background}`}}>{item.text}</div>
    </div>
    {item.diagnostics && <><div style={{position:"absolute",left:108,right:130,bottom:280,display:"flex",justifyContent:"space-between",
      color:paper,fontSize:24,letterSpacing:3,opacity:.78}}><span>{item.label}</span><span>12s / 30</span></div>
    <div style={{position:"absolute",left:108,right:130,bottom:252,height:2,background:"#ffffff18"}}>
      <div style={{height:2,width:`${globalFrame/359*100}%`,background:accent}}/>
    </div>
    </>}
    {phase!=="resolve" && <div style={{position:"absolute",top:-200,bottom:-200,left:`${-40+exit*170}%`,
      width:"18%",background:accent,transform:"skewX(-18deg)",opacity:exit>0?1:0}}/>}
  </AbsoluteFill>;
}
