"use client";

import {FormEvent, useCallback, useEffect, useState} from "react";
import {Activity, ArrowDownToLine, ArrowRight, CircleAlert, Clapperboard, Cpu, Film, FolderOpen, LayoutGrid, LockKeyhole, LogOut, Mic, Plus, Radio, RefreshCw, RotateCcw, Save, Sparkles, Upload} from "lucide-react";
import {api} from "@/lib/api";
import type {Asset, Channel, Engine, Job, Project, Scene, SystemStatus} from "@/lib/types";

type View = "overview" | "production" | "library" | "channels" | "system";
type Dialog = "project" | "channel" | null;
const nav = [
  {id: "overview", label: "Visão geral", Icon: LayoutGrid},
  {id: "production", label: "Produção", Icon: Clapperboard},
  {id: "library", label: "Biblioteca", Icon: FolderOpen},
  {id: "channels", label: "Canais", Icon: Radio},
  {id: "system", label: "Sistema", Icon: Activity},
] as const;
const pilotChannels: Array<{name: string; slug: string; niche: string; default_engine: Engine}> = [
  {name: "Futebol em Foco", slug: "futebol-em-foco", niche: "Futebol", default_engine: "football"},
  {name: "Mundo em Mapas", slug: "mundo-em-mapas", niche: "Geografia", default_engine: "geo"},
  {name: "Pulso Musical", slug: "pulso-musical", niche: "Música", default_engine: "music"},
];
const stateLabels: Record<string, string> = {IDEA:"Ideia", SCRIPTED:"Plano pronto", RENDERING:"Renderizando", QC:"Vídeo pronto", FAILED:"Falhou", QUEUED:"Na fila", RUNNING:"Em andamento", SUCCEEDED:"Concluído"};

export function ControlPanel() {
  const [view, setView] = useState<View>("overview");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [session, setSession] = useState<{authenticated:boolean;login_required:boolean} | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [newChannels, newProjects, newJobs, newSystem, newAssets] = await Promise.all([api.channels(),api.projects(),api.jobs(),api.system(),api.assets()]);
      setChannels(newChannels); setProjects(newProjects); setJobs(newJobs); setSystem(newSystem); setAssets(newAssets); setError(null);
    } catch (reason) { setError(message(reason)); }
  }, []);
  useEffect(() => { void api.session().then((value) => {setSession(value); if(value.authenticated) void load();}).catch((reason) => setError(message(reason))); }, [load]);
  useEffect(() => { if (!session?.authenticated) return; const interval = setInterval(() => {void load();}, 10000); return () => clearInterval(interval); }, [load,session]);
  const project = projects.find((item) => item.id === selected) ?? null;
  const openProject = (id: string) => {setSelected(id); setView("production");};
  const run = async (action: () => Promise<unknown>) => {setBusy(true);setError(null);try {await action();await load();} catch(reason) {setError(message(reason));} finally {setBusy(false);}};

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {await api.login(password);setSession({authenticated:true,login_required:true});setPassword("");});
  }
  async function handleLogout() { await run(async () => {await api.logout();setSession({authenticated:false,login_required:true});}); }
  async function createPilots() {
    await run(async () => {for (const pilot of pilotChannels) if (!channels.some((channel) => channel.slug === pilot.slug)) await api.createChannel(pilot);});
  }
  async function createChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    await run(async () => {await api.createChannel({name:data.get("name"),slug:data.get("slug"),niche:data.get("niche"),default_engine:data.get("engine")});setDialog(null);});
  }
  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    await run(async () => {const created = await api.createProject({channel_id:data.get("channel"),title:data.get("title"),topic:data.get("topic"),format:data.get("format")});await api.createPlan(created.id);setDialog(null);openProject(created.id);});
  }

  if (!session) return <div className="loading">Carregando MediaGrid…</div>;
  if (!session.authenticated) return <div className="login-screen"><form onSubmit={handleLogin} className="login-card"><Brand/><h1>Acesse seu estúdio</h1><p>Entre com a senha de administrador para gerenciar seus canais e projetos.</p><Field label="Senha"><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required/></Field>{error && <Alert text={error}/>}<button className="button primary full" disabled={busy}><LockKeyhole size={16}/> Entrar</button></form></div>;

  const navigate = (next: View) => {setView(next);setSelected(null);};
  return <div className="app">
    <aside className="sidebar">
      <button className="brand" onClick={() => navigate("overview")}><img className="brand-symbol" src="/brand-mark.svg" alt=""/><span className="brand-text"><strong>MediaGrid</strong><small>CONTENT OPERATING SYSTEM</small></span></button>
      <div className="nav-label">ESPAÇO DE TRABALHO</div><nav className="nav-list" aria-label="Menu principal">{nav.map(({id,label,Icon}) => <button key={id} className={`nav-item ${view===id?"active":""}`} onClick={() => navigate(id)}><Icon size={18}/>{label}</button>)}</nav>
      <div className="sidebar-bottom"><div className="mode-card"><span className="live-dot"/><span><strong>MediaGrid ativo</strong><small>{system?.mode ?? "Local"} · sem IA paga</small></span></div>{session.login_required&&<button className="nav-item" onClick={() => void handleLogout()}><LogOut size={18}/> Sair</button>}</div>
    </aside>
    <div className="main"><header className="topbar"><div><div className="eyebrow">MEDIAGRID / CONTROL PANEL</div><h1>{selected?project?.title:nav.find((item)=>item.id===view)?.label}</h1></div><div className="topbar-actions"><button className="button quiet" onClick={() => void load()} title="Atualizar"><RefreshCw size={16}/><span className="hide-mobile">Atualizar</span></button><button className="button primary" disabled={!channels.length} onClick={() => setDialog("project")}><Plus size={17}/> Criar conteúdo</button></div></header>
    <main className="content">{error && <Alert text={error}/>} {view==="overview" && <Overview channels={channels} projects={projects} jobs={jobs} system={system} onPilots={createPilots} onCreate={() => setDialog("project")} onProject={openProject} onNavigate={navigate} busy={busy}/>}
      {view==="production" && (project ? <ProjectEditor key={project.id} project={project} jobs={jobs.filter((job)=>job.project_id===project.id)} busy={busy} onBack={()=>setSelected(null)} onRefresh={load} onRun={run}/> : <Production projects={projects} channels={channels} onProject={openProject} onCreate={()=>setDialog("project")}/>)}
      {view==="library" && <Library assets={assets} jobs={jobs} system={system} busy={busy} onRun={run}/>}
      {view==="channels" && <Channels channels={channels} busy={busy} onCreate={()=>setDialog("channel")} onPilots={createPilots} onRun={run}/>}
      {view==="system" && <SystemView system={system} jobs={jobs} busy={busy} onRun={run}/>}
    </main></div>
    <nav className="mobile-nav" aria-label="Menu móvel">{nav.map(({id,label,Icon})=><button key={id} className={view===id?"active":""} onClick={()=>navigate(id)}><Icon size={19}/>{label}</button>)}</nav>
    {dialog && <div className="modal-backdrop" role="presentation" onMouseDown={(event)=>{if(event.target===event.currentTarget)setDialog(null);}}><form className="modal" onSubmit={dialog==="project"?createProject:createChannel}><div className="eyebrow">{dialog==="project"?"NOVA PRODUÇÃO":"NOVO CANAL"}</div><h2>{dialog==="project"?"Comece uma nova pauta":"Configure um canal"}</h2>{dialog==="project"?<><Field label="Canal"><select name="channel" required>{channels.map((channel)=><option key={channel.id} value={channel.id}>{channel.name}</option>)}</select></Field><Field label="Título"><input name="title" minLength={2} required placeholder="Ex.: O mapa que surpreendeu o mundo"/></Field><Field label="Pauta / briefing"><textarea name="topic" minLength={3} rows={4} required placeholder="Descreva o tema, objetivo e fatos que deseja abordar"/></Field><Field label="Formato"><select name="format"><option value="vertical">Vertical · Reels / Shorts / TikTok</option><option value="horizontal">Horizontal · YouTube</option><option value="square">Quadrado · Card</option><option value="carousel">Carrossel</option></select></Field></>:<><Field label="Nome"><input name="name" minLength={2} required placeholder="Nome do canal"/></Field><Field label="Identificador"><input name="slug" pattern="[a-z0-9]+(-[a-z0-9]+)*" required placeholder="nome-do-canal"/></Field><div className="field-grid"><Field label="Nicho"><input name="niche" required placeholder="Ex.: Futebol"/></Field><Field label="Engine"><select name="engine"><option value="football">Futebol</option><option value="geo">Geografia</option><option value="music">Música</option></select></Field></div></>}<div className="modal-actions"><button className="button" type="button" onClick={()=>setDialog(null)}>Cancelar</button><button className="button primary" disabled={busy} type="submit"><Plus size={15}/> Criar</button></div></form></div>}
  </div>;
}

function Overview({channels,projects,jobs,system,onPilots,onCreate,onProject,onNavigate,busy}:{channels:Channel[];projects:Project[];jobs:Job[];system:SystemStatus|null;onPilots:()=>void;onCreate:()=>void;onProject:(id:string)=>void;onNavigate:(view:View)=>void;busy:boolean}) {return <>
  <section className="hero"><div><div className="eyebrow">SEU ESTÚDIO DE CONTEÚDO</div><h2>Uma operação de conteúdo.<br/>Todos os seus canais.</h2><p>Planeje, organize e produza em um só lugar. Comece pela sua pauta e acompanhe cada etapa com clareza.</p></div><div className="hero-actions">{!channels.length?<button className="button primary" onClick={onPilots} disabled={busy}><Sparkles size={17}/> Criar 3 canais piloto</button>:<button className="button primary" onClick={onCreate}><Plus size={17}/> Nova produção</button>}</div></section>
  <div className="metric-grid"><Metric label="Canais" value={String(channels.length)} detail="Identidades editoriais" icon={Radio}/><Metric label="Projetos" value={String(projects.length)} detail="Pautas cadastradas" icon={Clapperboard}/><Metric label="Vídeos prontos" value={String(projects.filter((item)=>item.status==="QC").length)} detail="Para baixar e revisar" icon={Film}/><Metric label="Sistema" value={system?.ffmpeg?"Ativo":"Verificar"} detail={system?.dry_run?"Publicação em modo de teste":"Publicação ativa"} icon={Cpu}/></div>
  <div className="section-heading"><div><h2>Seu trabalho recente</h2><p>Acompanhe a produção e retome de onde parou.</p></div><button className="button small" onClick={()=>onNavigate("production")}>Abrir produção <ArrowRight size={14}/></button></div>
  <div className="two-col"><div className="panel"><div className="panel-head"><div><h3>Projetos</h3><p>Do briefing ao vídeo</p></div><span className="badge">{projects.length} no total</span></div>{projects.length?projects.slice(0,6).map((item)=><button key={item.id} className="row row-button" onClick={()=>onProject(item.id)}><span className="row-icon"><Film size={19}/></span><span className="row-main"><strong>{item.title}</strong><small>{channels.find((channel)=>channel.id===item.channel_id)?.name??"Canal"} · {item.format}</small></span><Badge value={item.status}/><ArrowRight size={16}/></button>):<Empty icon={Clapperboard} text="Nenhum projeto ainda. Crie os canais e depois sua primeira pauta."/>}</div><div className="panel"><div className="panel-head"><div><h3>Canais</h3><p>Operações em um mesmo lugar</p></div></div>{channels.length?channels.slice(0,5).map((channel)=><div key={channel.id} className="row"><span className="row-icon"><Radio size={18}/></span><span className="row-main"><strong>{channel.name}</strong><small>{channel.niche} · {channel.language}</small></span><span className="live-dot"/></div>):<Empty icon={Radio} text="Seus canais aparecerão aqui."/>}{jobs.some((job)=>job.status==="RUNNING")&&<p className="small-note side-note">Há renderizações em andamento. A tela atualiza automaticamente.</p>}</div></div>
</>}

function Production({projects,channels,onProject,onCreate}:{projects:Project[];channels:Channel[];onProject:(id:string)=>void;onCreate:()=>void}) {return <><div className="section-heading no-top"><div><h2>Produção</h2><p>Abra um projeto para editar seu plano, renderizar e baixar o vídeo.</p></div><button className="button primary" disabled={!channels.length} onClick={onCreate}><Plus size={16}/> Nova pauta</button></div><div className="panel">{projects.length?projects.map((project)=><button key={project.id} className="row row-button" onClick={()=>onProject(project.id)}><span className="row-icon"><Clapperboard size={19}/></span><span className="row-main"><strong>{project.title}</strong><small>{channels.find((channel)=>channel.id===project.channel_id)?.name??"Canal"} · {project.topic}</small></span><Badge value={project.status}/><ArrowRight size={16}/></button>):<Empty icon={Clapperboard} text="Ainda não há projetos. Crie uma pauta para começar."/>}</div></>}

function ProjectEditor({project,jobs,busy,onBack,onRefresh,onRun}:{project:Project;jobs:Job[];busy:boolean;onBack:()=>void;onRefresh:()=>Promise<void>;onRun:(action:()=>Promise<unknown>)=>Promise<void>}) {
  const [scenes,setScenes]=useState<Scene[]>(project.plan?.scenes??[]);
  const [hook,setHook]=useState(project.plan?.hook??"");
  const [angle,setAngle]=useState(project.plan?.angle??"");
  const latest=jobs[0];
  const edit=(index:number,field:keyof Scene,value:string)=>setScenes((current)=>current.map((scene,i)=>i===index?{...scene,[field]:field==="duration_seconds"?Number(value):value}:scene));
  const save=()=>onRun(async()=>{await api.updatePlan(project.id,{scenes,hook,angle});});
  const render=()=>onRun(async()=>{await api.render(project.id);});
  const voice=()=>onRun(async()=>{await api.voice(project.id);});
  const voiceReady=project.voice_ready;
  return <><button className="button quiet back" onClick={onBack}>← Voltar à produção</button><div className="section-heading no-top"><div><div className="eyebrow">PROJETO / {project.format.toUpperCase()}</div><h2>{project.title}</h2><p>{project.topic}</p></div><Badge value={project.status}/></div>
    <div className="detail-grid"><div className="panel editor-panel"><div className="panel-head"><div><h3>Plano de conteúdo</h3><p>Edite texto, duração e instruções de cada cena antes do render.</p></div><span className="badge">{scenes.length} cenas</span></div><div className="panel-body">{project.plan?<><Field label="Abertura"><input value={hook} onChange={(event)=>setHook(event.target.value)}/></Field><Field label="Ângulo editorial"><input value={angle} onChange={(event)=>setAngle(event.target.value)}/></Field>{scenes.map((scene,index)=><div className="scene-card" key={scene.id}><div className="scene-head"><span>CENA {String(index+1).padStart(2,"0")} · {scene.visual_type.toUpperCase()}</span><span>{scene.duration_seconds}s</span></div><div className="field-grid"><Field label="Texto na tela"><input value={scene.on_screen_text} onChange={(event)=>edit(index,"on_screen_text",event.target.value)}/></Field><Field label="Duração (segundos)"><input type="number" min="0.1" max="60" step="0.1" value={scene.duration_seconds} onChange={(event)=>edit(index,"duration_seconds",event.target.value)}/></Field></div><Field label="Narração"><textarea rows={3} value={scene.narration} onChange={(event)=>edit(index,"narration",event.target.value)}/></Field><Field label="Busca visual / referência"><input value={scene.visual_query} onChange={(event)=>edit(index,"visual_query",event.target.value)}/></Field></div>)}<div className="editor-actions"><button className="button" disabled={busy} onClick={()=>void save()}><Save size={16}/> Salvar alterações</button><button className="button primary" disabled={busy||latest?.status==="QUEUED"||latest?.status==="RUNNING"} onClick={()=>void render()}><Film size={16}/> Renderizar vídeo</button></div></>:<Empty icon={Clapperboard} text="Este projeto ainda não possui plano. Gere um plano para começar."/>}</div></div>
    <div className="aside-stack"><div className="panel"><div className="panel-head"><div><h3>Saída</h3><p>Arquivos produzidos neste computador</p></div></div><div className="panel-body"><p className="small-note">Gere a narração antes do render para incluí-la no MP4. Revise fatos e direitos antes de publicar.</p><button className="button full" disabled={busy||!project.script} onClick={()=>void voice()}><Mic size={16}/> Gerar voz local</button>{voiceReady&&<a className="button full" href={api.voiceFile(project.id)} download><ArrowDownToLine size={16}/> Baixar WAV</a>}{project.status==="QC"?<a className="button primary full" href={api.output(project.id)} download><ArrowDownToLine size={16}/> Baixar MP4</a>:<div className="output-wait"><Film size={23}/><span>Vídeo ainda não disponível</span></div>}</div></div><div className="panel"><div className="panel-head"><div><h3>Trabalhos</h3><p>Fila local de produção</p></div><button className="button small quiet" onClick={()=>void onRefresh()}><RefreshCw size={14}/></button></div>{jobs.length?jobs.map((job)=><div className="row" key={job.id}><span className="row-icon"><Cpu size={17}/></span><span className="row-main"><strong>{job.job_type} #{job.attempt}</strong><small>{job.error??new Date(job.created_at).toLocaleString("pt-BR")}</small></span><Badge value={job.status}/>{job.status==="FAILED"&&job.attempt<job.max_attempts&&<button className="button small" onClick={()=>void onRun(async()=>{await api.retry(job.id);})} title="Tentar novamente"><RotateCcw size={14}/></button>}</div>):<Empty icon={Cpu} text="Nenhum trabalho iniciado."/>}</div></div></div>
  </>;
}

function Library({assets,jobs,system,busy,onRun}:{assets:Asset[];jobs:Job[];system:SystemStatus|null;busy:boolean;onRun:(action:()=>Promise<unknown>)=>Promise<void>}) {
  const [selected,setSelected]=useState<File|null>(null);
  const [rights,setRights]=useState("UNKNOWN");
  const [transcript,setTranscript]=useState<string|null>(null);
  const [transcriptName,setTranscriptName]=useState("");
  const upload=()=>onRun(async()=>{if(!selected)return;const form=new FormData();form.append("file",selected);form.append("rights_status",rights);await api.uploadAsset(form);setSelected(null);});
  const showTranscript=(asset:Asset)=>onRun(async()=>{setTranscript(await api.transcript(asset.id));setTranscriptName(asset.name);});
  return <><div className="section-heading no-top"><div><h2>Biblioteca local</h2><p>Guarde arquivos no seu computador e registre os direitos de uso.</p></div><span className="badge">{assets.length} arquivos</span></div>
    <div className="panel"><div className="panel-head"><div><h3>Adicionar arquivo</h3><p>Áudio, vídeo, imagens e documentos até 500 MB</p></div><Upload size={20}/></div><div className="panel-body"><div className="field-grid"><Field label="Arquivo"><input type="file" onChange={(event)=>setSelected(event.target.files?.[0]??null)}/></Field><Field label="Direitos"><select value={rights} onChange={(event)=>setRights(event.target.value)}><option value="UNKNOWN">A verificar</option><option value="OWNED">Meu arquivo</option><option value="LICENSED">Licenciado</option><option value="RESTRICTED">Restrito</option></select></Field></div><button className="button primary" disabled={busy||!selected} onClick={()=>void upload()}><Upload size={16}/> Importar para biblioteca</button></div></div>
    <div className="section-heading"><div><h2>Arquivos</h2><p>Transcrição offline disponível para áudio e vídeo.</p></div></div><div className="panel">{assets.length?assets.map((asset)=><div className="row library-row" key={asset.id}><span className="row-icon"><FolderOpen size={18}/></span><span className="row-main"><strong>{asset.name}</strong><small>{asset.media_type} · {asset.rights_status} · {Math.round((asset.metadata_json.size_bytes??0)/1024)} KB</small></span><a className="button small" href={api.assetFile(asset.id)} download>Baixar</a>{(asset.media_type.startsWith("audio/")||asset.media_type.startsWith("video/"))&&<><button className="button small" disabled={busy||system?.transcription!=="AVAILABLE"} onClick={()=>void onRun(async()=>{await api.transcribe(asset.id);})}>Transcrever</button>{jobs.some((job)=>job.job_type==="TRANSCRIBE"&&job.result?.output?.includes(asset.id)&&job.status==="SUCCEEDED")&&<button className="button small" onClick={()=>void showTranscript(asset)}>Ver texto</button>}</>}</div>):<Empty icon={FolderOpen} text="Sua biblioteca ainda está vazia."/>}</div>{transcript!==null&&<div className="panel"><div className="panel-head"><h3>Transcrição · {transcriptName}</h3></div><div className="panel-body"><p style={{whiteSpace:"pre-wrap"}}>{transcript||"Nenhuma fala reconhecida."}</p></div></div>}</>;
}

function Channels({channels,busy,onCreate,onPilots,onRun}:{channels:Channel[];busy:boolean;onCreate:()=>void;onPilots:()=>void;onRun:(action:()=>Promise<unknown>)=>Promise<void>}) {
  const [editing,setEditing]=useState<string|null>(null);
  const [name,setName]=useState(""); const [tone,setTone]=useState(""); const [accent,setAccent]=useState("#c4d4ef"); const [autoRender,setAutoRender]=useState(false);
  const startEdit=(channel:Channel)=>{setEditing(channel.id);setName(channel.name);setTone(String(channel.editorial_profile.tone??""));setAccent(String(channel.brand_profile.accent??"#c4d4ef"));setAutoRender(channel.editorial_profile.auto_render===true);};
  return <><div className="section-heading no-top"><div><h2>Seus canais</h2><p>Configure a identidade visual e editorial de cada operação.</p></div><button className="button primary" onClick={onCreate}><Plus size={16}/> Novo canal</button></div>{!channels.length?<div className="panel empty"><Radio size={24}/>Você ainda não tem canais.<div className="empty-action"><button className="button primary" disabled={busy} onClick={()=>void onPilots()}>Criar os três canais piloto</button></div></div>:<div className="channel-grid">{channels.map((channel)=><div className="panel channel-card" key={channel.id}><div className="channel-icon" style={{borderColor:String(channel.brand_profile.accent??"#69798d")}}><Radio size={23}/></div><div className="eyebrow">{channel.default_engine.toUpperCase()} ENGINE</div><h3>{channel.name}</h3><p>{channel.niche} · {channel.language} · {channel.timezone}</p><div className="channel-card-bottom"><span className="badge green"><span className="live-dot"/> Ativo</span><button className="button small" onClick={()=>startEdit(channel)}>Configurar <ArrowRight size={13}/></button></div></div>)}</div>}{editing&&<div className="modal-backdrop" onMouseDown={(event)=>{if(event.target===event.currentTarget)setEditing(null);}}><form className="modal" onSubmit={(event)=>{event.preventDefault();void onRun(async()=>{await api.updateChannel(editing,{name,brand_profile:{accent},editorial_profile:{tone,auto_render:autoRender}});setEditing(null);});}}><div className="eyebrow">IDENTIDADE DO CANAL</div><h2>Configurar canal</h2><Field label="Nome"><input value={name} minLength={2} onChange={(event)=>setName(event.target.value)} required/></Field><Field label="Tom editorial"><input value={tone} onChange={(event)=>setTone(event.target.value)} placeholder="Ex.: informativo e direto"/></Field><Field label="Cor principal"><input value={accent} onChange={(event)=>setAccent(event.target.value)} pattern="#[0-9a-fA-F]{6}"/></Field><Field label="Automação local"><span><input type="checkbox" checked={autoRender} onChange={(event)=>setAutoRender(event.target.checked)}/> Renderizar automaticamente após gerar o plano</span></Field><div className="modal-actions"><button className="button" type="button" onClick={()=>setEditing(null)}>Cancelar</button><button className="button primary" type="submit" disabled={busy}><Save size={15}/> Salvar</button></div></form></div>}</>;
}

function SystemView({system,jobs,busy,onRun}:{system:SystemStatus|null;jobs:Job[];busy:boolean;onRun:(action:()=>Promise<unknown>)=>Promise<void>}) {return <><div className="section-heading no-top"><div><h2>Estado do sistema local</h2><p>Todos os serviços da V1 executam neste computador.</p></div></div><div className="metric-grid"><Metric label="Modo" value={system?.mode??"—"} detail="Acesso por localhost" icon={Activity}/><Metric label="FFmpeg" value={system?.ffmpeg?"Ativo":"Indisponível"} detail="Vídeo local" icon={Film}/><Metric label="Ollama" value={system?.ollama==="CONNECTED"?"Conectado":"Opcional"} detail="IA local" icon={Cpu}/><Metric label="Banco" value={system?.database??"—"} detail="Dados no computador" icon={Radio}/><Metric label="Voz" value={system?.tts==="AVAILABLE"?"Disponível":"Configurar"} detail="Síntese offline" icon={Mic}/><Metric label="Transcrição" value={system?.transcription==="AVAILABLE"?"Disponível":"Configurar"} detail="Reconhecimento offline" icon={Mic}/></div><div className="section-heading"><div><h2>Fila local</h2><p>O worker processa trabalhos e faz backup diário do banco em data/backups.</p></div></div><div className="panel">{jobs.length?jobs.map((job)=><div key={job.id} className="row"><span className="row-icon"><Film size={18}/></span><span className="row-main"><strong>{job.job_type} · {job.project_id?.slice(0,8)}</strong><small>{job.error??new Date(job.created_at).toLocaleString("pt-BR")}</small></span><Badge value={job.status}/>{job.status==="FAILED"&&job.attempt<job.max_attempts&&<button className="button small" disabled={busy} onClick={()=>void onRun(async()=>{await api.retry(job.id);})}><RotateCcw size={14}/> Repetir</button>}</div>):<Empty icon={Activity} text="Nenhum trabalho na fila."/>}</div><p className="small-note footer-note">A publicação em redes sociais permanece manual na V1. Nenhuma conta externa é necessária.</p></>}

function Metric({label,value,detail,icon:Icon}:{label:string;value:string;detail:string;icon:typeof Radio}) {return <div className="metric"><div className="metric-top"><span>{label.toUpperCase()}</span><Icon size={17}/></div><strong>{value}</strong><small>{detail}</small></div>}
function Badge({value}:{value:string}) {return <span className={`badge ${["QC","SUCCEEDED"].includes(value)?"green":["FAILED"].includes(value)?"orange":""}`}>{stateLabels[value]??value}</span>}
function Empty({icon:Icon,text}:{icon:typeof Radio;text:string}) {return <div className="empty"><Icon size={25}/>{text}</div>}
function Field({label,children}:{label:string;children:React.ReactNode}) {return <label className="field">{label}{children}</label>}
function Alert({text}:{text:string}) {return <div className="alert"><CircleAlert size={17}/>{text}</div>}
function Brand() {return <div className="brand static"><img className="brand-symbol" src="/brand-mark.svg" alt=""/><span className="brand-text"><strong>MediaGrid</strong><small>CONTENT OPERATING SYSTEM</small></span></div>}
function message(reason:unknown) {return reason instanceof Error?reason.message:"Ocorreu um erro. Tente novamente.";}
