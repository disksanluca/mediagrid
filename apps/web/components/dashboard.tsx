"use client";

import {FormEvent, useEffect, useState} from "react";
import {ArrowUpRight, CircleAlert, Clapperboard, Command, Cpu, Plus, RefreshCw, Radio, Sparkles} from "lucide-react";
import {api} from "@/lib/api";
import type {Channel, Engine, Project, SystemStatus} from "@/lib/types";

const starterChannels: Array<{name: string; slug: string; niche: string; engine: Engine}> = [
  {name: "Futebol em Foco", slug: "futebol-em-foco", niche: "Futebol", engine: "football"},
  {name: "Mundo em Mapas", slug: "mundo-em-mapas", niche: "Geografia", engine: "geo"},
  {name: "Pulso Musical", slug: "pulso-musical", niche: "Música", engine: "music"},
];

export function Dashboard() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [dialog, setDialog] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [channelData, projectData, systemData] = await Promise.all([api.channels(), api.projects(), api.system()]);
      setChannels(channelData); setProjects(projectData); setSystem(systemData); setError(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível acessar a API"); }
  };
  useEffect(() => { void load(); }, []);

  async function createPilots() {
    setBusy(true);
    try {
      for (const starter of starterChannels) {
        if (channels.some((channel) => channel.slug === starter.slug)) continue;
        await api.createChannel({name: starter.name, slug: starter.slug, niche: starter.niche, default_engine: starter.engine, brand_profile: {accent: starter.engine === "football" ? "#c6ff3d" : starter.engine === "geo" ? "#57d7e8" : "#d88bff"}, editorial_profile: {tone: "informativo e autoral"}});
      }
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao criar canais"); }
    finally { setBusy(false); }
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      const project = await api.createProject({channel_id: data.get("channel_id"), title: data.get("title"), topic: data.get("topic"), format: data.get("format"), content_type: "video"});
      await api.createPlan(project.id); setDialog(false); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Falha ao criar projeto"); }
    finally { setBusy(false); }
  }

  return <main className="min-h-screen lg:pl-64">
    <header className="flex h-20 items-center justify-between border-b border-[var(--line)] px-5 lg:px-9">
      <div><div className="text-xs font-bold tracking-[.22em] text-[var(--muted)]">CONTROL PANEL</div><h1 className="mt-1 text-xl font-bold">Visão geral</h1></div>
      <div className="flex items-center gap-3">
        <button className="hidden items-center gap-3 rounded-xl border border-[var(--line)] px-4 py-2.5 text-sm text-[var(--muted)] md:flex"><Command size={15}/> Buscar ou comandar <kbd className="rounded bg-white/8 px-1.5">⌘K</kbd></button>
        <button onClick={() => setDialog(true)} disabled={!channels.length} className="flex items-center gap-2 rounded-xl bg-[var(--lime)] px-4 py-2.5 text-sm font-black text-black disabled:opacity-40"><Plus size={17}/> CRIAR</button>
      </div>
    </header>

    <div className="mx-auto max-w-7xl p-5 lg:p-9">
      {error && <div className="mb-6 flex items-center justify-between rounded-xl border border-red-400/30 bg-red-400/8 p-4 text-sm text-red-200"><span className="flex items-center gap-2"><CircleAlert size={17}/>{error}</span><button onClick={() => void load()}><RefreshCw size={16}/></button></div>}
      <section className="mb-7 overflow-hidden rounded-2xl border border-[var(--line)] bg-[linear-gradient(115deg,#131a1d,#0e1315)] p-6 lg:p-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div><div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[var(--lime)]/20 bg-[var(--lime)]/7 px-3 py-1 text-xs font-bold text-[var(--lime)]"><span className="size-1.5 rounded-full bg-[var(--lime)]"/> AUTOPILOT FOUNDATION</div><h2 className="max-w-2xl text-3xl font-black leading-tight lg:text-4xl">Uma operação de conteúdo.<br/><span className="text-[var(--muted)]">Três canais, um sistema.</span></h2></div>
          {!channels.length && <button onClick={() => void createPilots()} disabled={busy} className="flex items-center justify-center gap-2 rounded-xl border border-[var(--lime)]/40 px-5 py-3 text-sm font-bold text-[var(--lime)] hover:bg-[var(--lime)]/8"><Sparkles size={17}/>{busy ? "Criando…" : "Criar canais piloto"}</button>}
        </div>
      </section>

      <section className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={Radio} label="Canais" value={String(channels.length)} detail="3 pilotos planejados"/>
        <Metric icon={Clapperboard} label="Projetos" value={String(projects.length)} detail={`${projects.filter((p) => p.status === "SCRIPTED").length} roteirizados`}/>
        <Metric icon={Cpu} label="IA local" value={system?.ollama === "CONNECTED" ? "ON" : "OFF"} detail={system?.ollama === "CONNECTED" ? "Ollama conectado" : "Fallback local ativo"}/>
        <Metric icon={Sparkles} label="Modo" value={system?.mode ?? "—"} detail={system?.dry_run ? "Publicação em dry-run" : "Publicação habilitada"}/>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_.8fr]">
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)]">
          <div className="flex items-center justify-between border-b border-[var(--line)] p-5"><div><h3 className="font-bold">Produção recente</h3><p className="mt-1 text-xs text-[var(--muted)]">Planos persistidos e prontos para edição</p></div><button className="text-xs font-bold text-[var(--lime)]">VER TUDO</button></div>
          <div className="divide-y divide-[var(--line)]">
            {projects.length ? projects.slice(0, 5).map((project) => <div key={project.id} className="flex items-center gap-4 p-5"><div className="grid size-11 place-items-center rounded-xl bg-white/5"><Clapperboard size={18}/></div><div className="min-w-0 flex-1"><div className="truncate text-sm font-bold">{project.title}</div><div className="mt-1 truncate text-xs text-[var(--muted)]">{project.topic}</div></div><Status value={project.status}/><ArrowUpRight size={16} className="text-[var(--muted)]"/></div>) : <div className="p-10 text-center text-sm text-[var(--muted)]">Crie os canais piloto e inicie sua primeira pauta.</div>}
          </div>
        </div>
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-5">
          <h3 className="font-bold">Canais</h3><p className="mt-1 text-xs text-[var(--muted)]">Identidades editoriais independentes</p>
          <div className="mt-5 space-y-3">{channels.map((channel) => <div key={channel.id} className="flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--panel-2)] p-3"><div className="grid size-9 place-items-center rounded-lg bg-white/5 text-sm font-black text-[var(--cyan)]">{channel.name[0]}</div><div className="flex-1"><div className="text-sm font-bold">{channel.name}</div><div className="text-[11px] uppercase tracking-wider text-[var(--muted)]">{channel.default_engine}</div></div><span className="size-2 rounded-full bg-[var(--lime)]"/></div>)}</div>
        </div>
      </section>
    </div>

    {dialog && <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm"><form onSubmit={createProject} className="w-full max-w-xl rounded-2xl border border-[var(--line)] bg-[#111719] p-6 shadow-2xl"><div className="mb-6"><div className="text-xs font-bold tracking-[.2em] text-[var(--lime)]">NOVO CONTEÚDO</div><h2 className="mt-2 text-2xl font-black">Transforme uma pauta em plano</h2></div><div className="space-y-4"><Field label="Canal"><select name="channel_id" required>{channels.map((channel) => <option value={channel.id} key={channel.id}>{channel.name}</option>)}</select></Field><Field label="Título interno"><input name="title" required placeholder="Ex.: Por que este mapa engana?"/></Field><Field label="Pauta"><textarea name="topic" required rows={4} placeholder="Descreva o assunto e o que você quer explicar"/></Field><Field label="Formato"><select name="format"><option value="vertical">Vertical — Shorts / Reels / TikTok</option><option value="horizontal">Horizontal — YouTube</option><option value="square">Quadrado — Card</option><option value="carousel">Carrossel</option></select></Field></div><div className="mt-6 flex justify-end gap-3"><button type="button" onClick={() => setDialog(false)} className="rounded-xl px-4 py-2.5 text-sm text-[var(--muted)]">Cancelar</button><button disabled={busy} className="rounded-xl bg-[var(--lime)] px-5 py-2.5 text-sm font-black text-black">{busy ? "CRIANDO…" : "CRIAR PLANO"}</button></div></form></div>}
  </main>;
}

function Metric({icon: Icon, label, value, detail}: {icon: typeof Radio; label: string; value: string; detail: string}) { return <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-5"><div className="flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">{label}</span><Icon size={17} className="text-[var(--cyan)]"/></div><div className="mt-4 text-3xl font-black">{value}</div><div className="mt-1 text-xs text-[var(--muted)]">{detail}</div></div>; }
function Status({value}: {value: string}) { return <span className="rounded-full border border-[var(--lime)]/20 bg-[var(--lime)]/7 px-2.5 py-1 text-[10px] font-bold text-[var(--lime)]">{value}</span>; }
function Field({label, children}: {label: string; children: React.ReactNode}) { return <label className="block text-xs font-bold text-[var(--muted)]">{label}<div className="mt-2 [&>*]:w-full [&>*]:rounded-xl [&>*]:border [&>*]:border-[var(--line)] [&>*]:bg-[#090d0f] [&>*]:px-3 [&>*]:py-3 [&>*]:text-sm [&>*]:text-white [&>*]:outline-none focus-within:[&>*]:border-[var(--lime)]/50">{children}</div></label>; }

