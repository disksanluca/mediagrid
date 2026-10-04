import type {Channel, ContentPlan, Job, Project, SystemStatus} from "./types";

const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
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
  system: () => request<SystemStatus>("/system"),
  createChannel: (body: Record<string, unknown>) => request<Channel>("/channels", {method: "POST", body: JSON.stringify(body)}),
  updateChannel: (id: string, body: Record<string, unknown>) => request<Channel>(`/channels/${id}`, {method: "PATCH", body: JSON.stringify(body)}),
  createProject: (body: Record<string, unknown>) => request<Project>("/projects", {method: "POST", body: JSON.stringify(body)}),
  createPlan: (id: string) => request<ContentPlan>(`/projects/${id}/plan`, {method: "POST"}),
  updatePlan: (id: string, body: Record<string, unknown>) => request<Project>(`/projects/${id}/plan`, {method: "PUT", body: JSON.stringify(body)}),
  render: (id: string) => request<{job_id: string; status: string}>(`/projects/${id}/render`, {method: "POST"}),
  retry: (id: string) => request<Job>(`/jobs/${id}/retry`, {method: "POST"}),
  output: (id: string) => `${baseUrl}/projects/${id}/output`,
};
