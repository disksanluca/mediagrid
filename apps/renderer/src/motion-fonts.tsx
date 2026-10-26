import {useEffect,useState} from "react";
import {cancelRender,continueRender,delayRender} from "remotion";
import {sportsFontData} from "./sports-font";
import {spaceFontData} from "./space-font";
import {plexFontData} from "./plex-font";
export const motionFonts={
  "Barlow Condensed":{family:"MG Barlow",weight:700,data:sportsFontData},
  "Space Grotesk":{family:"MG Space",weight:400,data:spaceFontData},
  "IBM Plex Sans":{family:"MG Plex",weight:400,data:plexFontData},
} as const;
export type MotionFontName=keyof typeof motionFonts;
const loaded=new Map<string,Promise<void>>();
function load(name:MotionFontName){
  let promise=loaded.get(name);
  if(!promise){
    const f=motionFonts[name];
    promise=new FontFace(f.family,`url(${f.data})`,{weight:String(f.weight)}).load()
      .then(face=>{document.fonts.add(face);});
    loaded.set(name,promise);
  }
  return promise;
}
export function MotionFonts({families}:{families:MotionFontName[]}){
  const key=[...new Set(families)].sort().join("|");
  const [handle]=useState(()=>delayRender("Loading licensed local Motion fonts"));
  useEffect(()=>{
    void Promise.all(key.split("|").filter(Boolean).map(name=>load(name as MotionFontName)))
      .then(()=>continueRender(handle))
      .catch(error=>cancelRender(error instanceof Error?error:new Error(String(error))));
  },[key,handle]);
  return null;
}

