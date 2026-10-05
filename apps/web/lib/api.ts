import type {Asset, Channel, ContentPlan, HardwareProfile, Job, Project, SetupState, SystemStatus} from "./types";
import {desktopRuntime} from "./desktop";

let baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

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
    const body = (await response.json().catch(() => null)) as {detail?: string} | null;
    throw new Error(body?.detail ?? `Erro ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  session: () => request<{authenticated: boolean; login_required: boolean}>("/auth/session"),
  login: (password: string) => request<{authenticated: boolean}>("/auth/login", {method: "POST", body: JSON.stringify({password})}),
  logout: () => request<{authenticated: boolean}>("/auth/logout", {method: "POST"}),
  channels: () => request<Channel[]>("/channels"),
  projects: () => request<Project[]>("/projects"),
  jobs: () => request<Job[]>("/jobs"),
  assets: () => request<Asset[]>("/assets"),
  uploadAsset: async (form: FormData) => {
    const response = await fetch(`${await resolveBaseUrl()}/assets`, {method:"POST", body:form});
    if (!response.ok) {const body = (await response.json().catch(()=>null)) as {detail?:string}|null; throw new Error(body?.detail ?? `Erro ${response.status}`);}
    return response.json() as Promise<Asset>;
  },
  assetFile: (id: string) => `${baseUrl}/assets/${id}/file`,
  transcribe: (id: string) => request<{job_id:string;status:string}>(`/assets/${id}/transcribe`, {method:"POST"}),
  transcript: async (id: string) => {
    const response = await fetch(`${await resolveBaseUrl()}/assets/${id}/transcript`);
    if (!response.ok) throw new Error("Transcrição ainda não disponível.");
    return response.text();
  },
  system: () => request<SystemStatus>("/system"),
  hardware: () => request<HardwareProfile>("/system/hardware"),
  setup: () => request<SetupState>("/system/setup"),
  completeSetup: (profile: HardwareProfile["recommended_profile"]) => request<SetupState>("/system/setup", {method:"POST", body:JSON.stringify({profile})}),
  createChannel: (body: Record<string, unknown>) => request<Channel>("/channels", {method: "POST", body: JSON.stringify(body)}),
  updateChannel: (id: string, body: Record<string, unknown>) => request<Channel>(`/channels/${id}`, {method: "PATCH", body: JSON.stringify(body)}),
  createProject: (body: Record<string, unknown>) => request<Project>("/projects", {method: "POST", body: JSON.stringify(body)}),
  createPlan: (id: string) => request<ContentPlan>(`/projects/${id}/plan`, {method: "POST"}),
  updatePlan: (id: string, body: Record<string, unknown>) => request<Project>(`/projects/${id}/plan`, {method: "PUT", body: JSON.stringify(body)}),
  render: (id: string) => request<{job_id: string; status: string}>(`/projects/${id}/render`, {method: "POST"}),
  voice: (id: string) => request<{job_id: string; status: string}>(`/projects/${id}/voice`, {method:"POST"}),
  voiceFile: (id: string) => `${baseUrl}/projects/${id}/voice`,
  retry: (id: string) => request<Job>(`/jobs/${id}/retry`, {method: "POST"}),
  output: (id: string) => `${baseUrl}/projects/${id}/output`,
};
