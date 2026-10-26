import type {Asset, CaptionCue, Channel, ClipCandidate, ContentPlan, CreativeBrief, CreativeDNA, CreativeDecision, CreativeDirections, CreativeReview, CreativeRevision, CreativeStoryboard, CreativeStoryboardRevision, DoctorReport, FootballSequence, FootballShot, GeoMunicipality, HardwareProfile, Job, KnowledgeClaim, MusicDraftSchedule, MusicReleaseGroup, Narrative3DSequence, Narrative3DShot, OfficialProposal, PreviewResponse, Project, SetupState, SystemStatus, TimedTranscript, TimelineResponse, TranscriptWord, WikiTopPage} from "./types";
import {desktopRuntime} from "./desktop";

export interface UploadState {
  id: string;
  name: string;
  size_bytes: number;
  received_bytes: number;
  status: "OPEN" | "COMPLETE" | "FAILED";
  asset_id: string | null;
  error: string | null;
  rights_status: string;
  creator: string | null;
  source_url: string | null;
  license_name: string | null;
  commercial_use: boolean;
}

let baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(readonly status:number, readonly detail:unknown) {
    super(errorMessage(detail,status));
    this.name="ApiError";
  }
}

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const issues = detail.filter((issue): issue is {loc?: unknown;msg: string} =>
      typeof issue === "object" && issue !== null && typeof issue.msg === "string");
    const labels:Record<string,string>={topic:"tópico",audience:"público",objective:"objetivo",duration_ms:"duração",sources:"fontes",url:"URL",title:"título",palette:"paleta",tone:"tom",shots:"planos",beat:"beat",visual_description:"descrição visual",asset_ids:"assets",claim_ids:"alegações"};
    const translate=(msg:string)=>msg.replace(/^Field required$/,"campo obrigatório").replace(/^String should have at least (\d+) characters$/,"mínimo de $1 caracteres").replace(/^String should have at most (\d+) characters$/,"máximo de $1 caracteres").replace(/^Input should be a valid URL.*/,"URL inválida");
    if (issues.length) return issues.map((issue) => {
      const path=Array.isArray(issue.loc)?issue.loc.filter((part)=>part!=="body").map((part)=>labels[String(part)]??part).join(" › "):"Campo";
      return `${path}: ${translate(issue.msg)}`;
    }).join("; ");
  }
  if (typeof detail === "object" && detail !== null) {
    const value=detail as {code?:unknown;reasons?:unknown;current_revision?:unknown};
    const reasons=Array.isArray(value.reasons)?value.reasons.join("; "):"";
    return [value.code, value.current_revision !== undefined?`revisão atual ${value.current_revision}`:null, reasons].filter(Boolean).join(" · ") || `Erro ${status}`;
  }
  return `Erro ${status}`;
}

async function resolveBaseUrl(): Promise<string> {
  const runtime = await desktopRuntime();
  if (runtime) baseUrl = `http://127.0.0.1:${runtime.api_port}/api/v1`;
  return baseUrl;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${await resolveBaseUrl()}${path}`, {
    ...init,
    headers: {"Content-Type": "application/json", ...init?.headers},
    cache: "no-store",
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {detail?: unknown} | null;
    throw new ApiError(response.status, body?.detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  session: () => request<{authenticated: boolean; login_required: boolean}>("/auth/session"),
  login: (password: string) => request<{authenticated: boolean}>("/auth/login", {method: "POST", body: JSON.stringify({password})}),
  logout: () => request<{authenticated: boolean}>("/auth/logout", {method: "POST"}),
  channels: () => request<Channel[]>("/channels"),
  creativeDNA: (channelId:string) => request<CreativeRevision<CreativeDNA>>(`/channels/${channelId}/creative-dna`),
  saveCreativeDNA: (channelId:string, expected_revision:number, content:CreativeDNA) =>
    request<CreativeRevision<CreativeDNA>>(`/channels/${channelId}/creative-dna`, {method:"PUT",body:JSON.stringify({expected_revision,content})}),
  creativeBrief: (projectId:string) => request<CreativeRevision<CreativeBrief>>(`/projects/${projectId}/creative/brief`),
  saveCreativeBrief: (projectId:string, expected_revision:number, content:CreativeBrief) =>
    request<CreativeRevision<CreativeBrief>>(`/projects/${projectId}/creative/brief`, {method:"PUT",body:JSON.stringify({expected_revision,content})}),
  creativeDirections: (projectId:string) => request<CreativeDirections>(`/projects/${projectId}/creative/directions`),
  generateCreativeDirections: (projectId:string, expected_revision:number, expected_brief_revision:number, expected_dna_revision:number) =>
    request<CreativeDirections>(`/projects/${projectId}/creative/directions`,{method:"POST",body:JSON.stringify({expected_revision,expected_brief_revision,expected_dna_revision})}),
  creativeStoryboard: (projectId:string) => request<CreativeStoryboardRevision>(`/projects/${projectId}/creative/storyboard`),
  saveCreativeStoryboard: (projectId:string, expected_revision:number, expected_direction_revision:number, content:CreativeStoryboard) =>
    request<CreativeStoryboardRevision>(`/projects/${projectId}/creative/storyboard`,{method:"PUT",body:JSON.stringify({expected_revision,expected_direction_revision,content})}),
  creativeReview: (projectId:string) => request<CreativeReview>(`/projects/${projectId}/creative/review`),
  decideCreative: (projectId:string, body:CreativeDecision) =>
    request<CreativeReview>(`/projects/${projectId}/creative/decision`,{method:"POST",body:JSON.stringify(body)}),
  projects: () => request<Project[]>("/projects"),
  jobs: () => request<Job[]>("/jobs"),
  job: (id:string) => request<Job>(`/jobs/${id}`),
  assets: () => request<Asset[]>("/assets"),
  createUpload: (body: {name:string;media_type:string;size_bytes:number;rights_status:string;creator:string|null;source_url:string|null;license_name:string|null;commercial_use:boolean}) =>
    request<UploadState>("/assets/uploads", {method:"POST", body:JSON.stringify(body)}),
  uploadState: (id: string) => request<UploadState>(`/assets/uploads/${id}`),
  uploadChunk: async (id: string, offset: number, chunk: Blob) => {
    const response = await fetch(`${await resolveBaseUrl()}/assets/uploads/${id}`, {
      method:"PUT", headers:{"Upload-Offset":String(offset),"Content-Type":"application/octet-stream"}, body:chunk,
    });
    if (!response.ok) {const body=(await response.json().catch(()=>null)) as {detail?:unknown}|null;throw new Error(errorMessage(body?.detail,response.status));}
    return response.json() as Promise<UploadState>;
  },
  completeUpload: (id: string) => request<{upload:UploadState;asset_id:string;proxy_job_id:string|null}>(`/assets/uploads/${id}/complete`, {method:"POST"}),
  uploadAsset: async (form: FormData) => {
    const response = await fetch(`${await resolveBaseUrl()}/assets`, {method:"POST", body:form});
    if (!response.ok) {const body = (await response.json().catch(()=>null)) as {detail?:unknown}|null; throw new Error(errorMessage(body?.detail,response.status));}
    return response.json() as Promise<Asset>;
  },
  assetFile: (id: string) => `${baseUrl}/assets/${id}/file`,
  assetProxy: (id: string) => `${baseUrl}/assets/${id}/proxy`,
  assetWaveform: (id: string) => `${baseUrl}/assets/${id}/waveform`,
  updateAssetRights: (id: string, body: {rights_status:string;creator:string|null;source_url?:string|null;license_name:string|null;commercial_use:boolean}) => request<Asset>(`/assets/${id}/rights`, {method:"PATCH",body:JSON.stringify(body)}),
  transcribe: (id: string) => request<{job_id:string;status:string}>(`/assets/${id}/transcribe`, {method:"POST"}),
  transcript: async (id: string) => {
    const response = await fetch(`${await resolveBaseUrl()}/assets/${id}/transcript`);
    if (!response.ok) throw new Error("Transcrição ainda não disponível.");
    return response.text();
  },
  asrStatus: () => request<{word_asr_available:boolean;engine:string}>("/assets/asr-status"),
  transcribeWords: (id:string) => request<{job_id:string;status:string}>(`/assets/${id}/transcribe-words`, {method:"POST"}),
  transcriptV2: async (id:string): Promise<TimedTranscript|null> => {
    const response=await fetch(`${await resolveBaseUrl()}/assets/${id}/transcript-v2`,{cache:"no-store"});
    if(response.status===404)return null;
    if(!response.ok){const body=(await response.json().catch(()=>null)) as {detail?:unknown}|null;throw new Error(errorMessage(body?.detail,response.status));}
    return response.json() as Promise<TimedTranscript>;
  },
  saveTranscript: (id:string, body:{expected_revision:number;language:string;words:TranscriptWord[];cues:CaptionCue[]}) =>
    request<TimedTranscript>(`/assets/${id}/transcript-v2`,{method:"PUT",body:JSON.stringify(body)}),
  approveCaptions: (id:string, revision:number) =>
    request<TimedTranscript>(`/assets/${id}/captions/approve`,{method:"POST",body:JSON.stringify({expected_revision:revision})}),
  captionFile: (id:string,format:"srt"|"vtt") => `${baseUrl}/assets/${id}/captions.${format}`,
  renderCaptions: (id:string,revision:number) => request<{job_id:string;status:string}>(`/assets/${id}/captions/render`,{method:"POST",body:JSON.stringify({expected_revision:revision})}),
  captionRenderStatus: (id:string) => request<{job_id:string;status:string;error:string|null}|null>(`/assets/${id}/captions/render-status`),
  captionVideo: (id:string,jobId:string) => `${baseUrl}/assets/${id}/captions/render/${jobId}`,
  analyzeClips: (id:string) => request<{job_id:string;status:string}>(`/assets/${id}/clips/analyze`,{method:"POST"}),
  clips: (id:string) => request<ClipCandidate[]>(`/assets/${id}/clips`),
  updateClip: (assetId:string,clipId:string,body:{expected_revision:number;action:"edit"|"select"|"reject";start_ms?:number;end_ms?:number;aspect?:"source"|"vertical";focus_x?:number;focus_y?:number}) =>
    request<ClipCandidate>(`/assets/${assetId}/clips/${clipId}`,{method:"PATCH",body:JSON.stringify(body)}),
  renderClip: (assetId:string,clipId:string,revision:number) =>
    request<{job_id:string;status:string}>(`/assets/${assetId}/clips/${clipId}/render`,{method:"POST",body:JSON.stringify({expected_revision:revision})}),
  clipRenderStatus: (assetId:string,clipId:string) =>
    request<{job_id:string;status:string;error:string|null}|null>(`/assets/${assetId}/clips/${clipId}/render-status`),
  clipVideo: (assetId:string,clipId:string,jobId:string) => `${baseUrl}/assets/${assetId}/clips/${clipId}/render/${jobId}`,
  football: (projectId:string) => request<FootballSequence|null>(`/projects/${projectId}/football`),
  saveFootball: (projectId:string,body:{expected_revision:number;aspect:"horizontal"|"vertical";shots:FootballShot[];score_label:string|null;score_source_url:string|null}) =>
    request<FootballSequence>(`/projects/${projectId}/football`,{method:"PUT",body:JSON.stringify(body)}),
  approveFootball: (projectId:string,revision:number,scoreVerified:boolean) =>
    request<FootballSequence>(`/projects/${projectId}/football/approve`,{method:"POST",body:JSON.stringify({expected_revision:revision,events_verified:true,rights_confirmed:true,score_verified:scoreVerified})}),
  renderFootball: (projectId:string) => request<{job_id:string;status:string}>(`/projects/${projectId}/football/render`,{method:"POST"}),
  footballRenderStatus: (projectId:string) => request<{job_id:string;status:string;error:string|null}|null>(`/projects/${projectId}/football/render-status`),
  footballVideo: (projectId:string,jobId:string) => `${baseUrl}/projects/${projectId}/football/render/${jobId}`,
  narrative3d: (projectId:string) => request<Narrative3DSequence|null>(`/projects/${projectId}/narrative-3d`),
  saveNarrative3d: (projectId:string,body:{expected_revision:number;title:string;aspect:"vertical"|"horizontal";shots:Narrative3DShot[];audio_asset_id:string|null}) =>
    request<Narrative3DSequence>(`/projects/${projectId}/narrative-3d`,{method:"PUT",body:JSON.stringify(body)}),
  queueNarrative3d: (projectId:string,quality:"blocking"|"final") =>
    request<{job_id:string;status:string}>(`/projects/${projectId}/narrative-3d/${quality}`,{method:"POST"}),
  approveNarrative3d: (projectId:string,revision:number) =>
    request<Narrative3DSequence>(`/projects/${projectId}/narrative-3d/approve-blocking`,{method:"POST",body:JSON.stringify({expected_revision:revision,watched_full_preview:true,character_continuity_checked:true,story_timing_checked:true})}),
  narrative3dStatus: (projectId:string,quality:"blocking"|"final") =>
    request<{job_id:string;status:string;progress:number;error:string|null}|null>(`/projects/${projectId}/narrative-3d/${quality}/render-status`),
  narrative3dVideo: (projectId:string,quality:"blocking"|"final",jobId:string) =>
    `${baseUrl}/projects/${projectId}/narrative-3d/${quality}/render/${jobId}`,
  claims: (projectId:string) => request<KnowledgeClaim[]>(`/projects/${projectId}/claims`),
  addClaim: (projectId:string,body:Omit<KnowledgeClaim,"id"|"project_id"|"revision"|"status"|"reviewed_at"|"source_checked_at">) =>
    request<KnowledgeClaim>(`/projects/${projectId}/claims`,{method:"POST",body:JSON.stringify(body)}),
  saveClaim: (projectId:string,claimId:string,body:Omit<KnowledgeClaim,"id"|"project_id"|"revision"|"status"|"reviewed_at"|"source_checked_at"> & {expected_revision:number}) =>
    request<KnowledgeClaim>(`/projects/${projectId}/claims/${claimId}`,{method:"PUT",body:JSON.stringify(body)}),
  approveClaim: (projectId:string,claimId:string,revision:number) =>
    request<KnowledgeClaim>(`/projects/${projectId}/claims/${claimId}/approve`,{method:"POST",body:JSON.stringify({expected_revision:revision,source_opened:true,excerpt_matches:true,context_checked:true})}),
  removeClaim: (projectId:string,claimId:string,revision:number) =>
    request<KnowledgeClaim>(`/projects/${projectId}/claims/${claimId}/remove`,{method:"POST",body:JSON.stringify({expected_revision:revision})}),
  system: () => request<SystemStatus>("/system"),
  voiceStatus: () => request<{available:boolean;voices:string[];voice_name:string|null;rate:number}>("/system/voice"),
  setVoice: (voice_name:string,rate:number) => request<{available:boolean;voices:string[];voice_name:string|null;rate:number}>("/system/voice",{method:"PUT",body:JSON.stringify({voice_name,rate})}),
  blenderStatus: () => request<{available:boolean;path:string|null;required_version:string}>("/system/blender"),
  setBlender: (path:string) => request<{available:boolean;path:string;required_version:string}>("/system/blender",{method:"PUT",body:JSON.stringify({path})}),
  hardware: () => request<HardwareProfile>("/system/hardware"),
  doctor: (internet=false) => request<DoctorReport>(`/system/doctor?internet=${internet}`),
  setup: () => request<SetupState>("/system/setup"),
  completeSetup: (profile: HardwareProfile["recommended_profile"]) => request<SetupState>("/system/setup", {method:"POST", body:JSON.stringify({profile})}),
  createChannel: (body: Record<string, unknown>) => request<Channel>("/channels", {method: "POST", body: JSON.stringify(body)}),
  updateChannel: (id: string, body: Record<string, unknown>) => request<Channel>(`/channels/${id}`, {method: "PATCH", body: JSON.stringify(body)}),
  createProject: (body: Record<string, unknown>) => request<Project>("/projects", {method: "POST", body: JSON.stringify(body)}),
  createMotionAd: (body: {channel_id:string;format:"vertical"|"horizontal";product_name:string;audience:string;hook:string;problem:string;benefit:string;call_to_action:string;brand_color:string}) =>
    request<Project>("/motion-ads/projects", {method:"POST", body:JSON.stringify(body)}),
  politicsProposals: (query: string, year: number) => request<OfficialProposal[]>(`/politics/proposals?query=${encodeURIComponent(query)}&year=${year}`),
  importPoliticsProposal: (channelId: string, proposalId: number) => request<Project>("/politics/projects", {method:"POST", body:JSON.stringify({channel_id:channelId,proposal_id:proposalId})}),
  geoMunicipalities: (query: string) => request<GeoMunicipality[]>(`/geo/municipalities?query=${encodeURIComponent(query)}`),
  importGeoMunicipality: (channelId: string, municipalityId: number) => request<Project>("/geo/projects", {method:"POST", body:JSON.stringify({channel_id:channelId,municipality_id:municipalityId})}),
  musicReleaseGroups: (query: string) => request<MusicReleaseGroup[]>(`/music/release-groups?query=${encodeURIComponent(query)}`),
  importMusicReleaseGroup: (channelId: string, releaseGroupId: string) => request<Project>("/music/projects", {method:"POST", body:JSON.stringify({channel_id:channelId,release_group_id:releaseGroupId})}),
  musicDraftSchedules: () => request<MusicDraftSchedule[]>("/music/drafts/schedules"),
  scheduleMusicDraft: (channelId:string,releaseGroupId:string,scheduledAt:string) => request<MusicDraftSchedule>("/music/drafts/schedules", {method:"POST",body:JSON.stringify({channel_id:channelId,release_group_id:releaseGroupId,scheduled_at:scheduledAt})}),
  cancelMusicDraft: (id:string) => request<MusicDraftSchedule>(`/music/drafts/schedules/${id}/cancel`,{method:"POST"}),
  retryMusicDraft: (id:string) => request<MusicDraftSchedule>(`/music/drafts/schedules/${id}/retry`,{method:"POST"}),
  wikiTopPages: (day: string, query: string) => request<WikiTopPage[]>(`/trends/wiki-top?day=${encodeURIComponent(day)}&query=${encodeURIComponent(query)}`),
  importWikiTopPage: (channelId: string, day: string, article: string) => request<Project>("/trends/projects", {method:"POST", body:JSON.stringify({channel_id:channelId,day,article})}),
  createPlan: (id: string) => request<ContentPlan>(`/projects/${id}/plan`, {method: "POST"}),
  updatePlan: (id: string, body: Record<string, unknown>) => request<Project>(`/projects/${id}/plan`, {method: "PUT", body: JSON.stringify(body)}),
  timeline: (id: string) => request<TimelineResponse>(`/projects/${id}/edl-v2`),
  preview: (id: string) => request<PreviewResponse>(`/projects/${id}/preview`),
  updateTimeline: (id: string, body: {expected_revision:number;expected_legacy_sha256:string;edl:TimelineResponse["edl"]}) => request<{revision:number;sha256:string;project_id:string}>(`/projects/${id}/edl-v2`, {method:"PUT", body:JSON.stringify(body)}),
  render: (id: string) => request<{job_id: string; status: string}>(`/projects/${id}/render`, {method: "POST"}),
  voice: (id: string) => request<{job_id: string; status: string}>(`/projects/${id}/voice`, {method:"POST"}),
  importRecordedVoice: async (id: string, file: File, rightsConfirmed: boolean, scriptConfirmed: boolean): Promise<Project> => {
    const body = new FormData();
    body.append("file", file);
    body.append("rights_confirmed", String(rightsConfirmed));
    body.append("script_confirmed", String(scriptConfirmed));
    const response = await fetch(`${await resolveBaseUrl()}/projects/${id}/voice/recorded`, {
      method: "POST", body, cache: "no-store",
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as {detail?: unknown} | null;
      throw new Error(errorMessage(payload?.detail, response.status));
    }
    return response.json() as Promise<Project>;
  },
  voiceFile: (id: string) => `${baseUrl}/projects/${id}/voice`,
  retry: (id: string) => request<Job>(`/jobs/${id}/retry`, {method: "POST"}),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}/cancel`, {method: "POST"}),
  output: (id: string) => `${baseUrl}/projects/${id}/output`,
  approveReview: (id: string, body: {source_urls:string[];facts_confirmed:boolean;rights_confirmed:boolean;notes:string;caption:string}) => request<Project>(`/projects/${id}/review`, {method:"POST", body:JSON.stringify(body)}),
  exportPackage: (id: string) => `${baseUrl}/projects/${id}/export`,
};
