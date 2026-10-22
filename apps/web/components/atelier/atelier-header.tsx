"use client";

import {ChartNoAxesCombined, Clapperboard, LogOut, Monitor, Network, Radar, RefreshCw, Search, Settings, Sparkles, Workflow} from "lucide-react";
import type {LucideIcon} from "lucide-react";

export const atelierNav = [
  {id: "studio", label: "Studio", Icon: Monitor},
  {id: "editor", label: "Editor", Icon: Clapperboard},
  {id: "motion", label: "Motions", Icon: Sparkles},
  {id: "radar", label: "Radar", Icon: Radar},
  {id: "network", label: "Network", Icon: Network},
  {id: "control", label: "Control", Icon: Workflow},
  {id: "insights", label: "Insights", Icon: ChartNoAxesCombined},
  {id: "settings", label: "Settings", Icon: Settings},
] as const satisfies ReadonlyArray<{id: string; label: string; Icon: LucideIcon}>;

export type AtelierView = (typeof atelierNav)[number]["id"] | "library";

interface Props {
  view: AtelierView;
  mode: string | null;
  loginRequired: boolean;
  onNavigate: (view: AtelierView) => void;
  onCommand: () => void;
  onRefresh: () => void;
  onLogout: () => void;
}

export function AtelierHeader({view, mode, loginRequired, onNavigate, onCommand, onRefresh, onLogout}: Props) {
  return <header className="atelier-header">
    <button className="brand" onClick={() => onNavigate("studio")} aria-label="Abrir Studio">
      <img className="brand-symbol" src="/brand-mark.svg" alt=""/>
      <span className="brand-text"><strong>MediaGrid</strong><small>ATELIER OS / PRIVATE</small></span>
    </button>
    <nav className="atelier-nav" aria-label="Espaços de trabalho">
      {atelierNav.map(({id, label, Icon}) => <button key={id} className={view === id ? "active" : ""} onClick={() => onNavigate(id)} aria-current={view === id ? "page" : undefined}>
        <Icon size={20} strokeWidth={1.75} aria-hidden="true"/><span>{label}</span>
      </button>)}
    </nav>
    <div className="atelier-header-actions">
      <button className="atelier-icon-button" onClick={onCommand} title="Navegação rápida (Ctrl+K)" aria-label="Abrir navegação rápida"><Search size={17} strokeWidth={1.75}/></button>
      <span className="atelier-local"><span className="live-dot"/>{mode ?? "Local"}</span>
      <button className="atelier-icon-button atelier-refresh" onClick={onRefresh} aria-label="Atualizar dados" title="Atualizar dados"><RefreshCw size={16} strokeWidth={1.75}/></button>
      {loginRequired && <button className="atelier-icon-button" onClick={onLogout} aria-label="Sair" title="Sair"><LogOut size={16} strokeWidth={1.75}/></button>}
    </div>
  </header>;
}
