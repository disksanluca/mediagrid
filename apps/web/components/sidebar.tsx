"use client";

import {Activity, Aperture, Blocks, BookImage, LayoutDashboard, Radio, Settings2, Sparkles} from "lucide-react";

const nav = [
  [LayoutDashboard, "Dashboard"], [Aperture, "Produção"], [Radio, "Radar"],
  [BookImage, "Biblioteca"], [Blocks, "Templates"], [Activity, "Sistema"],
] as const;

export function Sidebar() {
  return <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-[var(--line)] bg-[#090d0f]/90 p-5 backdrop-blur lg:block">
    <div className="mb-10 flex items-center gap-3 px-2">
      <div className="grid size-10 place-items-center rounded-xl bg-[var(--lime)] text-black"><Sparkles size={19}/></div>
      <div><div className="text-lg font-black tracking-[.18em]">MEDIAGRID</div><div className="text-[10px] tracking-[.28em] text-[var(--muted)]">CONTENT OS</div></div>
    </div>
    <nav className="space-y-1">
      {nav.map(([Icon, label], index) => <button key={label} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm ${index === 0 ? "bg-white/8 text-white" : "text-[var(--muted)] hover:bg-white/5 hover:text-white"}`}><Icon size={17}/>{label}</button>)}
    </nav>
    <div className="absolute bottom-5 left-5 right-5 rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3 text-xs text-[var(--muted)]">
      <div className="mb-1 flex items-center gap-2 font-bold text-[var(--lime)]"><span className="size-2 rounded-full bg-[var(--lime)]"/> ZERO COST</div>
      Local-first ativo
    </div>
  </aside>;
}

