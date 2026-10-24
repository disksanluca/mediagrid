import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import type {RenderOverlay} from "./types";

type RigProps={luma:boolean;expression:string;mouth:string;pose:string;color:string;
  unit:number;bob:number;characterName:string;horizontal:boolean;paired?:boolean};

function CharacterRig({luma,expression,mouth,pose,color,unit,bob,characterName,horizontal,paired=false}:RigProps){
  const browY=expression==="surprised"?-13:expression==="skeptical"?7:0;
  return <svg viewBox="0 0 480 600" role="img" aria-label={`Personagem vetorial ${characterName}`}
        style={{order:horizontal?1:1,width:paired?"82%":horizontal?"42%":"73%",maxHeight:paired?"60%":horizontal?"100%":"65%",
          overflow:"visible",objectFit:"contain",filter:"drop-shadow(0 18px 28px #0008)",transform:`translateY(${bob*unit}px)`}}>
        <ellipse cx="240" cy="575" rx="142" ry="18" fill="#000" opacity=".3"/>
        <path d={luma?"M153 364 Q81 418 134 527 Q240 585 346 527 Q399 418 327 364Z":
          "M151 362 Q104 423 130 527 Q240 580 350 527 Q377 422 329 362Z"}
          fill={color} stroke="#0a151a" strokeWidth="12"/>
        {luma?<><path d="M82 230 Q65 125 191 113 H289 Q415 125 398 230 L382 337 Q374 398 294 398 H186 Q106 398 98 337Z"
          fill="#203c48" stroke="#0a151a" strokeWidth="13"/>
          <circle cx="81" cy="267" r="24" fill={color} stroke="#0a151a" strokeWidth="9"/>
          <circle cx="399" cy="267" r="24" fill={color} stroke="#0a151a" strokeWidth="9"/></>
          :<rect x="58" y="119" width="364" height="278" rx="115" fill="#172934"
            stroke="#0a151a" strokeWidth="13"/>}
        <path d="M117 231 Q139 172 202 178 M277 178 Q340 172 363 231"
          stroke="#84b6ae" strokeWidth="6" fill="none" opacity=".5"/>
        <path d={`M135 ${190+browY} L210 ${expression==="skeptical"?205:190+browY}`}
          stroke={color} strokeWidth="13" strokeLinecap="round"/>
        <path d={`M270 ${expression==="skeptical"?205:190+browY} L346 ${190+browY}`}
          stroke={color} strokeWidth="13" strokeLinecap="round"/>
        <ellipse cx="172" cy="249" rx="31" ry={expression==="surprised"?39:expression==="happy"?22:29} fill="#f8faf6"/>
        <ellipse cx="308" cy="249" rx="31" ry={expression==="surprised"?39:expression==="happy"?22:29} fill="#f8faf6"/>
        <circle cx="176" cy="252" r="12" fill="#101923"/>
        <circle cx="312" cy="252" r="12" fill="#101923"/>
        {luma&&<><circle cx="130" cy="293" r="13" fill={color} opacity=".65"/>
          <circle cx="350" cy="293" r="13" fill={color} opacity=".65"/></>}
        {mouth==="round"?<ellipse cx="240" cy="322" rx="25" ry="34" fill="#090e13"/>
          :mouth==="open"?<ellipse cx="240" cy="326" rx="55" ry="28" fill="#090e13"/>
            :mouth==="smile"?<path d="M190 316 Q240 361 290 316" stroke="#f8faf6"
              strokeWidth="12" strokeLinecap="round" fill="none"/>
              :<path d="M198 321 L282 321" stroke="#f8faf6" strokeWidth="10"
                strokeLinecap="round"/>}
        <path d={pose==="point"?"M154 410 Q64 390 42 215 L84 212 Q112 344 178 440Z":
          pose==="shrug"?"M154 410 Q50 391 42 335 L78 318 Q105 372 178 440Z":
            "M154 410 Q72 424 70 529 L111 529 Q115 465 178 440Z"}
          fill={color} stroke="#0a151a" strokeWidth="11"/>
        <path d={pose==="shrug"?"M326 410 Q430 391 438 335 L402 318 Q375 372 302 440Z":
          "M326 410 Q408 424 410 529 L369 529 Q365 465 302 440Z"}
          fill={color} stroke="#0a151a" strokeWidth="11"/>
        {luma?<path d="M208 114 Q222 38 240 47 Q258 38 272 114Z" fill={color}
          stroke="#0a151a" strokeWidth="9"/>:<><rect x="209" y="88" width="62" height="38" rx="18" fill={color}/>
          <circle cx="240" cy="75" r="27" fill={color} stroke="#0a151a" strokeWidth="9"/></>}
      </svg>;
}

/** Original versioned SVG rig. Mouth motion follows only editor supplied cues. */
export function CharacterDialogue({item}: {item: RenderOverlay}) {
  const frame=useCurrentFrame();
  const {fps,width,height}=useVideoConfig();
  const time=frame*1000/fps;
  const cue=item.mouth_cues?.find((part)=>time>=part.start_ms&&time<part.end_ms);
  const luma=item.character_id==="luma_v1";
  const characterName=luma?"LUMA":"MIGO";
  const expression=item.expression??"neutral";
  const mouth=cue?.viseme??(expression==="happy"?"smile":"closed");
  const pose=item.pose??"idle";
  const points=item.keyframes.map((keyframe)=>Math.round(keyframe.at_ms*fps/1000));
  const value=(key:"x"|"y"|"opacity"|"scale")=>interpolate(frame,points,
    item.keyframes.map((keyframe)=>keyframe[key]),
    {extrapolateLeft:"clamp",extrapolateRight:"clamp"});
  const unit=width/1080;
  const horizontal=width>height;
  const bob=Math.sin(frame/9)*5;
  if(item.partner_character_id){
    const partnerLuma=item.partner_character_id==="luma_v1";
    const partnerName=partnerLuma?"LUMA":"MIGO";
    const partnerExpression=item.partner_expression??"neutral";
    const partnerCue=item.partner_mouth_cues?.find((part)=>time>=part.start_ms&&time<part.end_ms);
    const partnerMouth=partnerCue?.viseme??(partnerExpression==="happy"?"smile":"closed");
    const dialogue=[{name:characterName,luma,color:item.color,text:item.text,expression,pose,mouth},
      {name:partnerName,luma:partnerLuma,color:item.partner_color??"#80d5ed",
        text:item.partner_text??"",expression:partnerExpression,pose:item.partner_pose??"idle",
        mouth:partnerMouth}];
    return <AbsoluteFill style={{zIndex:item.z_index,pointerEvents:"none",background:"#101e29",
      color:"#f8faf6",fontFamily:"Arial, sans-serif"}}>
      <div style={{position:"absolute",inset:0,opacity:.15,
        backgroundImage:"radial-gradient(#c8f777 2px, transparent 2px)",
        backgroundSize:`${36*unit}px ${36*unit}px`}}/>
      <div style={{position:"absolute",left:`${value("x")*100}%`,top:`${value("y")*100}%`,
        transform:`translate(-50%,-50%) scale(${value("scale")})`,opacity:value("opacity"),
        width:"91%",height:horizontal?"84%":"76%",display:"flex",alignItems:"stretch",
        justifyContent:"center",gap:horizontal?42*unit:24*unit}}>
        {dialogue.map((speaker,index)=><div key={speaker.name} style={{flex:1,minWidth:0,
          display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:20*unit}}>
          <div style={{width:"100%",minHeight:horizontal?184*unit:270*unit,
            boxSizing:"border-box",border:`3px solid ${speaker.color}`,
            borderRadius:28*unit,background:"#f7f9f0",color:"#101923",
            padding:`${(horizontal?24:30)*unit}px ${(horizontal?30:25)*unit}px`,
            boxShadow:"0 25px 60px #0008"}}>
            <div style={{fontSize:(horizontal?20:24)*unit,fontWeight:900,letterSpacing:2*unit,
              color:"#51653b",marginBottom:12*unit}}>{speaker.name} · FALA {index+1}</div>
            <div style={{fontSize:(horizontal?36:45)*unit,fontWeight:900,lineHeight:1.08,
              overflowWrap:"break-word"}}>{speaker.text}</div>
          </div>
          <CharacterRig luma={speaker.luma} expression={speaker.expression} mouth={speaker.mouth}
            pose={speaker.pose} color={speaker.color} unit={unit} bob={bob+(index?3:0)}
            characterName={speaker.name} horizontal={horizontal} paired/>
        </div>)}
      </div>
      <div style={{position:"absolute",bottom:40*unit,right:48*unit,fontSize:19*unit,
        letterSpacing:2*unit,color:"#a5b6b0"}}>RIGS ORIGINAIS · MIGO + LUMA V1</div>
    </AbsoluteFill>;
  }
  return <AbsoluteFill style={{zIndex:item.z_index,pointerEvents:"none",background:luma?"#14212d":"#101923",
    color:"#f8faf6",fontFamily:"Arial, sans-serif"}}>
    <div style={{position:"absolute",inset:0,opacity:.19,
      backgroundImage:"radial-gradient(#c8f777 2px, transparent 2px)",
      backgroundSize:`${36*unit}px ${36*unit}px`}}/>
    <div style={{position:"absolute",left:`${value("x")*100}%`,top:`${value("y")*100}%`,
      transform:`translate(-50%,-50%) scale(${value("scale")})`,opacity:value("opacity"),
      width:horizontal?"74%":"84%",height:horizontal?"88%":"76%",maxWidth:1500,
      display:"flex",flexDirection:horizontal?"row":"column",alignItems:"center",
      justifyContent:"center",gap:horizontal?28*unit:8*unit}}>
      <div style={{order:horizontal?2:0,flex:horizontal?1:undefined,minWidth:0,
        width:horizontal?"52%":"100%",border:`3px solid ${item.color}`,
        borderRadius:32*unit,background:"#f7f9f0",color:"#101923",
        boxShadow:"0 25px 60px #0008",padding:`${(horizontal?40:44)*unit}px ${(horizontal?42:50)*unit}px`,
        boxSizing:"border-box"}}>
        <div style={{color:"#51653b",fontSize:25*unit,fontWeight:900,
          letterSpacing:3*unit,marginBottom:20*unit}}>{characterName} / CENA 2D</div>
        <div style={{fontSize:(horizontal?38:66)*unit,fontWeight:900,lineHeight:1.08,
          overflowWrap:"break-word"}}>{item.text}</div>
      </div>
      <CharacterRig luma={luma} expression={expression} mouth={mouth} pose={pose}
        color={item.color} unit={unit} bob={bob} characterName={characterName} horizontal={horizontal}/>
    </div>
    <div style={{position:"absolute",bottom:40*unit,right:48*unit,fontSize:19*unit,
      letterSpacing:2*unit,color:"#a5b6b0"}}>{`RIG ORIGINAL · ${characterName} V1`}</div>
  </AbsoluteFill>;
}
