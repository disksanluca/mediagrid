import {AbsoluteFill, useCurrentFrame, useVideoConfig} from "remotion";
import type {RenderOverlay} from "./types";

// Analytic, frame-addressable 2.5D scene within the existing EDL overlay.
// No simulation state, randomness at render time, extra timeline or renderer.
type V = [number, number, number];
const add = (a:V,b:V):V => [a[0]+b[0],a[1]+b[1],a[2]+b[2]];
const mul = (a:V,s:number):V => [a[0]*s,a[1]*s,a[2]*s];
const dot = (a:V,b:V) => a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross = (a:V,b:V):V => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit = (a:V) => mul(a,1/Math.hypot(...a));
const clamp = (x:number) => Math.min(1,Math.max(0,x));
const smooth = (x:number) => {const v=clamp(x);return v*v*(3-2*v);};
const easeOut = (x:number) => 1-Math.pow(1-clamp(x),3);
const range = (t:number,a:number,b:number) => smooth((t-a)/(b-a));
const mix = (a:number,b:number,p:number) => a+(b-a)*p;
function curve(t:number, points:number[][]):number[] {
  if(t<=points[0][0]) return points[0].slice(1);
  for(let i=1;i<points.length;i++) {
    if(t<=points[i][0]) {const p=range(t,points[i-1][0],points[i][0]);
      return points[i].slice(1).map((v,j)=>mix(points[i-1][j+1],v,p));}
  }
  return points[points.length-1].slice(1);
}
const impulse = (t:number, at:number, decay=7) => t<at?0:Math.exp(-(t-at)*decay);

// Truncated icosahedron panels, projected from a rotating sphere. All geometry
// is constructed here. Great-circle interpolation gives curved, foreshortened seams.
const phi=(1+Math.sqrt(5))/2;
const vertices:V[]=[];
for(const a of [-1,1]) for(const b of [-phi,phi])
  vertices.push([0,a,b],[a,b,0],[b,0,a]);
const adjacent=(a:V,b:V)=>Math.abs(Math.hypot(...add(a,mul(b,-1)))-2)<.001;
const panelFaces:V[][]=[];
for(const v of vertices) {
  const n=unit(v), axis=unit(cross(n,[.13,.57,1])), other=cross(n,axis);
  const near=vertices.filter(w=>adjacent(v,w)).map(w=>unit(add(mul(v,2),w)));
  near.sort((a,b)=>Math.atan2(dot(a,other),dot(a,axis))-Math.atan2(dot(b,other),dot(b,axis)));
  panelFaces.push(near);
}
for(let i=0;i<12;i++) for(let j=i+1;j<12;j++) for(let k=j+1;k<12;k++) {
  const a=vertices[i],b=vertices[j],c=vertices[k];
  if(adjacent(a,b)&&adjacent(b,c)&&adjacent(a,c))
    panelFaces.push([add(mul(a,2),b),add(mul(b,2),a),add(mul(b,2),c),
      add(mul(c,2),b),add(mul(c,2),a),add(mul(a,2),c)].map(unit));
}
function rotate(v:V,y:number,x:number):V {
  const a=v[0]*Math.cos(y)+v[2]*Math.sin(y), z=-v[0]*Math.sin(y)+v[2]*Math.cos(y);
  return [a,v[1]*Math.cos(x)-z*Math.sin(x),v[1]*Math.sin(x)+z*Math.cos(x)];
}
function LeatherBall({x,y,r,turn,accent}:{x:number;y:number;r:number;turn:number;accent:string}) {
  const faces=panelFaces.map((face,i)=>{
    const n=rotate(unit(face.reduce(add,[0,0,0])),turn,.32+turn*.22);
    const points:V[]=[];
    face.forEach((a,k)=>{const b=face[(k+1)%face.length];
      for(let s=0;s<8;s++) points.push(rotate(unit(add(mul(a,1-s/8),mul(b,s/8))),turn,.32+turn*.22));});
    const light=Math.max(0,dot(n,unit([-.5,-.7,1])));
    const level=i<12?Math.round(16+light*24):Math.round(105+light*142);
    return {i,n,points,fill:i<12?`rgb(${level*.7},${level},${level*.95})`:`rgb(${level},${level+Math.min(4,255-level)},${level*.96})`};
  }).filter(f=>f.n[2]>-.22).sort((a,b)=>a.n[2]-b.n[2]);
  return <g transform={`translate(${x} ${y}) scale(${r})`}>
    <defs><clipPath id="ball-edge"><circle r="1"/></clipPath>
      <radialGradient id="ball-light" cx="28%" cy="22%" r="82%">
        <stop stopColor="#fff" stopOpacity=".28"/><stop offset=".4" stopColor="#fff" stopOpacity="0"/>
        <stop offset=".86" stopColor="#00100f" stopOpacity=".16"/><stop offset="1" stopColor="#00100f" stopOpacity=".8"/>
      </radialGradient></defs>
    <circle r="1" fill="#1e3933"/>
    <g clipPath="url(#ball-edge)">
      {faces.map(f=><path key={f.i} d={f.points.map((v,i)=>`${i?"L":"M"}${v[0]} ${v[1]}`).join(" ")+"Z"}
        fill={f.fill} stroke="#0c221d" strokeWidth=".009" strokeLinejoin="round"/>)}
      <circle r="1" fill="url(#ball-light)"/>
      <ellipse cx="-.32" cy="-.5" rx=".23" ry=".055" transform="rotate(-30)" fill="#fff" opacity=".16"/>
    </g>
    <circle r=".998" fill="none" stroke={accent} strokeOpacity=".22" strokeWidth=".008"/>
  </g>;
}
export function SportsRefinement({item}:{item:RenderOverlay}) {
  const local=useCurrentFrame()/useVideoConfig().fps;
  const t=local+item.start_ms/1000;
  const energetic=item.art_direction==="broadcast";
  const accent=item.color,paper=item.paper??"#F4F0E6",bg=item.background??"#0B1013";
  const phase=item.phase??"impact";
  const duration=item.duration_ms/1000;
  const cam=curve(t,energetic?[
    [0,-60,30,1,-5],[1.6,30,-10,1.09,-2],[2,100,-30,1.2,5],[3.8,-70,20,.98,-3],
    [4.7,-40,20,1,0],[5,70,-40,1.12,-9],[6.35,-55,5,1.03,4],[7.55,60,-20,1.16,-5],
    [8.65,-40,10,1.1,5],[9,0,0,1,0],[10.1,0,0,1.08,-2],[11.97,25,0,1.02,0],
  ]:[
    [0,-35,15,1,0],[1.7,20,-10,1.045,-2],[3.5,55,-25,1.1,1],
    [5,-30,10,.98,-5],[6.65,25,0,1.025,0],[8.7,-30,-25,1.09,3],
    [9.4,0,0,1.02,0],[11.97,20,-5,1.05,-1],
  ]);
  // Three depth planes see different displacement under the same camera.
  const project=(x:number,y:number,z:number):[number,number,number]=>{
    const s=1200/(1200+z)*cam[2];
    const angle=cam[3]*Math.PI/180;
    const px=(x-cam[0])*s,py=(y-cam[1])*s;
    return [540+px*Math.cos(angle)-py*Math.sin(angle),960+px*Math.sin(angle)+py*Math.cos(angle),s];
  };
  const ball=curve(t,[
    [0,780,1180,72],[1.35,730,1090,100],[2,590,860,250],
    [3.5,490,800,270],[4.25,470,820,245],[5,300,1380,82],
    [5.8,310,1350,86],[6.45,540,1120,115],[7.05,500,1100,95],
    [7.7,765,910,105],[8.25,740,950,110],[9,540,1080,192],
    [9.65,540,1170,170],[10.5,650,1240,127],[11.25,790,1300,88],[11.97,818,1306,84],
  ]);
  const ballOffset=project(ball[0]-540,ball[1]-960,0);
  const bx=ballOffset[0],by=ballOffset[1],br=ball[2]*ballOffset[2];
  const hits=[0,2,5,6.45,7.7,9,10.5];
  const kick=hits.reduce((a,s)=>a+impulse(t,s,8),0);
  const fieldOpacity=range(t,4.3,5.15)*(1-range(t,9,10.1));
  const orbitOpacity=1-range(t,4.1,5.1);
  const follow=energetic?1:.55;
  const end=range(t,10.9,11.65); // A deliberate, readable final settling interval.
  const grid=(z:number)=>project(0,0,z);
  const back=grid(1000),front=grid(-320);
  const titleEnter=easeOut((local-(phase==="impact"?.07:phase==="resolve"?.2:.12))/(energetic?.26:.5));
  // Clear the type before the ball travels across its plane; avoid ghost letters
  // over the reveal. The remaining time belongs to the visual transition.
  const titleExit=phase==="resolve"?0:phase==="impact"?range(local,1.3,1.62)
    :phase==="reveal"?range(local,2.18,2.52):range(local,duration-.38,duration-.08);
  const titleY=phase==="impact"?510:phase==="reveal"?1240:phase==="play"?355:565;
  const lines=item.text.split("\n");
  const longest=Math.max(...lines.map(l=>l.length));
  const fontSize=Math.min(phase==="impact"?228:phase==="resolve"?200:184,1420/longest);
  // The text remains in a fixed 108..950 safe frame, independent of camera shake.
  return <AbsoluteFill style={{background:bg,overflow:"hidden",zIndex:item.z_index,fontFamily:'"MG Barlow", sans-serif',fontWeight:700}}>
    <svg viewBox="0 0 1080 1920" style={{position:"absolute",width:"100%",height:"100%"}}>
      <defs>
        <radialGradient id="haze"><stop stopColor="#406e60" stopOpacity=".55"/>
          <stop offset="1" stopColor={bg} stopOpacity="0"/></radialGradient>
        <linearGradient id="floor" x1="0" y1="0" x2=".7" y2="1"><stop stopColor="#16392f"/><stop offset="1" stopColor={bg}/></linearGradient>
        <radialGradient id="vignette"><stop offset=".4" stopColor="#000" stopOpacity="0"/><stop offset="1" stopColor="#000" stopOpacity=".66"/></radialGradient>
        <linearGradient id="beam"><stop stopColor={accent} stopOpacity="0"/><stop offset=".55" stopColor={accent} stopOpacity=".12"/><stop offset="1" stopColor={paper} stopOpacity="0"/></linearGradient>
        <filter id="soft"><feGaussianBlur stdDeviation="24"/></filter>
        <filter id="foreground-soft"><feGaussianBlur stdDeviation="7"/></filter>
        <radialGradient id="shadow"><stop stopColor="#000" stopOpacity=".72"/><stop offset="1" stopColor="#000" stopOpacity="0"/></radialGradient>
      </defs>
      {/* Background: distant stadium architecture and volumetric light. */}
      <ellipse cx={back[0]+140} cy={back[1]-130} rx="850" ry="1150" fill="url(#haze)"/>
      <g transform={`translate(${back[0]} ${back[1]}) scale(${back[2]})`} stroke={paper} fill="none">
        {[-1000,-650,-300,50,400,750,1100].map((x,i)=><path key={i}
          d={`M${x} -1500L${x-220} 1550`} strokeOpacity=".055" strokeWidth="3"/>)}
        {[0,1,2].map(i=><ellipse key={i} cx="0" cy={-650+i*120} rx={1050+i*250} ry={240+i*60} strokeOpacity=".08" strokeWidth="3"/>)}
      </g>
      <path d={`M${-280+back[0]*.1} -100L${450+back[0]*.1} -100L${1100+back[0]*.2} 1920L${650+back[0]*.2} 1920Z`}
        fill="url(#beam)" opacity={.8+kick*.2}/>
      {energetic&&t>=9&&<g transform={`translate(540 ${1370-range(t,9,9.45)*80}) rotate(${-14+range(t,9,11)*5})`}>
        <rect x="-900" y="-90" width="1800" height={170+range(t,9,10.3)*130} fill={accent}/>
        <path d="M-900 -120H900 M-900 250H900" stroke={paper} strokeWidth="2" opacity=".6"/>
      </g>}
      {/* Midground orbit becomes the field: shared camera carries the transition. */}
      <g opacity={orbitOpacity} transform={`translate(${bx} ${by+40}) rotate(${-22+t*3})`}>
        <ellipse rx={br+170} ry={(br+170)*.4} fill="none" stroke={accent} strokeWidth="2" opacity=".45"/>
        <ellipse rx={br+190} ry={(br+190)*.42} fill="none" stroke={paper} strokeWidth="1" opacity=".12"/>
        <path d={`M${-br-190} 0h60 M${br+130} 0h60`} stroke={accent} strokeWidth="5"/>
      </g>
      <g opacity={fieldOpacity} transform={`translate(${project(0,230,190)[0]} ${project(0,230,190)[1]}) rotate(${-12+cam[3]*2}) scale(${cam[2]})`}>
        <path d="M-260 -470H260L440 450H-440Z" fill="url(#floor)" stroke={paper} strokeOpacity=".36" strokeWidth="2"/>
        <path d="M-350 0H350 M-110 -470L-135 -290H135L110 -470 M-200 450L-175 250H175L200 450"
          fill="none" stroke={paper} strokeOpacity=".28" strokeWidth="2"/>
        <ellipse rx="100" ry="80" fill="none" stroke={paper} strokeOpacity=".32" strokeWidth="2"/>
        {Array.from({length:7},(_,i)=><path key={i} d={`M${-260-i*24} ${-470+i*130}H${260+i*24}`}
          stroke={paper} strokeOpacity=".035" strokeWidth="50"/>)}
      </g>
      {/* Route is driven by the same event times as the moving ball and score. */}
      {t>=5&&t<10&&<g opacity={1-range(t,9,10)}>
        <path d={`M${project(-240,420,0)[0]} ${project(-240,420,0)[1]} L${project(0,160,0)[0]} ${project(0,160,0)[1]} L${project(225,-50,0)[0]} ${project(225,-50,0)[1]}`}
          fill="none" stroke={accent} strokeWidth="4" pathLength="1"
          strokeDasharray="1" strokeDashoffset={1-range(t,5.35,7.7)} opacity=".8"/>
        {[[5, -240,420],[6.45,0,160],[7.7,225,-50]].map(([at,x,y],i)=>{
          const p=project(x,y,0),a=impulse(t,at,2.5);
          return <g key={i} opacity={range(t,at-.25,at)}>
            <ellipse cx={p[0]} cy={p[1]+50} rx={35+a*95} ry={12+a*32}
              fill="none" stroke={accent} strokeWidth={2+a*3} opacity={.25+a*.6}/>
            <text x={p[0]-65} y={p[1]+110} fill={paper} fontSize="22" opacity=".65">0{i+1}</text>
          </g>;
        })}
      </g>}
      {/* Contact shadow tightens as the ball approaches its plane. */}
      <ellipse cx={bx+br*.12} cy={by+br+42} rx={br*1.3} ry={br*.22} fill="url(#shadow)" opacity=".85"/>
      {hits.filter(at=>at>=5).map((at,i)=>{
        const p=range(t,at,at+.7),op=t>=at?(1-p)*.5:0;
        return <ellipse key={i} cx={bx} cy={by+br*.7} rx={br+400*p} ry={br*.28+160*p}
          fill="none" stroke={accent} strokeWidth={3*(1-p)+1} opacity={op}/>;
      })}
      <LeatherBall x={bx} y={by} r={br} turn={.2+t*(energetic?1.1:.52)+range(t,5,9)*2.4} accent={accent}/>
      {/* Sparse, directed particles: proximity to ball and impact determines displacement. */}
      {Array.from({length:28},(_,i)=>{
        const angle=i*2.39996;
        const distance=br+80+(i%5)*30+kick*50*follow;
        const z=(i%3)*240-150;
        const p=project(ball[0]-540+Math.cos(angle+t*.09)*distance,
          ball[1]-960+Math.sin(angle+t*.09)*distance*.66,z);
        return <circle key={i} cx={p[0]} cy={p[1]} r={(i%3+1)*p[2]*.65}
          fill={i%4===0?accent:paper} opacity={.1+kick*.16}/>;
      })}
      {/* Foreground: dark defocused rails cross faster than distant architecture. */}
      <g filter="url(#foreground-soft)" opacity=".68" transform={`translate(${(front[0]-540)*2} ${(front[1]-960)*.7}) rotate(${cam[3]*.4})`}>
        <path d="M-170 -150L-25 -150L120 2100H-70Z" fill="#020b0a"/>
        <path d="M1130 -150L1200 -150L1020 2100H980Z" fill="#020b0a"/>
        <path d="M-20 1520L1120 1770" stroke="#030e0b" strokeWidth="16" opacity=".55"/>
      </g>
      <rect width="1080" height="1920" fill="url(#vignette)"/>
      {/* Climax ring grows beyond the image, followed by an intentional settled lockup. */}
      {t>=9&&<g fill="none" stroke={accent}>
        <circle cx="540" cy="1060" r={180+range(t,9,10.6)*1000} opacity={.55*(1-range(t,9.2,10.6))} strokeWidth={mix(12,1,range(t,9,10.6))}/>
        <path d={`M${150+end*30} 1515H${150+range(t,9.4,11.4)*780}`} strokeWidth="3" opacity=".7"/>
      </g>}
      {energetic&&[1.92,4.92,8.92].map((at,i)=>{
        const p=clamp((t-at)/.14);
        if(p<=0||p>=1)return null;
        if(i===1) return <circle key={i} cx={bx} cy={by} r={p*1800}
          fill="none" stroke={paper} strokeWidth={Math.sin(p*Math.PI)*140} opacity={(1-p)*.7}/>;
        if(i===2) return <rect key={i} width="1080" height="1920" fill={accent}
          opacity={Math.sin(p*Math.PI)*.17}/>;
        return <path key={i} d={`M${-900+p*2500} -100h65L${-1100+p*2500} 2020h-65Z`}
          fill={accent} opacity=".85"/>;
      })}
    </svg>
    <div style={{position:"absolute",left:108,top:titleY,width:842,
      color:paper,opacity:(1-titleExit),transform:`translateY(${(1-titleEnter)*(energetic?25:46)-titleExit*20}px)`}}>
      <div style={{fontSize:24,letterSpacing:6,color:accent,marginBottom:26,opacity:titleEnter,
        transform:`translateX(${(1-titleEnter)*-16}px)`}}>
        {phase==="impact"?"O INSTANTE ANTES":phase==="reveal"?"ENERGIA EM MOVIMENTO":phase==="play"?"CRIE O PRÓXIMO LANCE":"SEU MOVIMENTO COMEÇA"}
      </div>
      {lines.map((line,i)=>{
        const enter=easeOut((local-.1-i*(energetic?.055:.11))/(energetic?.28:.52));
        return <div key={i} style={{overflow:"hidden",paddingBottom:10,marginBottom:-10}}>
          <div style={{fontSize,lineHeight:.97,letterSpacing:energetic?-1:-2,
            whiteSpace:"pre",transformOrigin:"left center",
            transform:`translateY(${(1-enter)*112}%) skewX(${energetic?-6:-2}deg) scaleX(${.97+.03*enter})`,
            textShadow:"0 4px 28px #0009"}}>{line}</div>
        </div>;
      })}
    </div>
    {item.diagnostics&&<div style={{position:"absolute",inset:0,pointerEvents:"none",color:accent,fontSize:22}}>
      <div style={{position:"absolute",left:108,right:130,top:240,bottom:280,border:"1px dashed #d7ff3f77"}}/>
      <div style={{position:"absolute",left:108,top:180}}>MEDIAGRID / {item.art_direction?.toUpperCase()} / {t.toFixed(3)}s</div>
      <div style={{position:"absolute",left:108,bottom:180}}>DIAGNÓSTICO · 3 PLANOS · 12s / 30fps</div>
    </div>}
  </AbsoluteFill>;
}

