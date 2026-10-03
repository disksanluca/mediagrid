import type {Channel, Project, SystemStatus} from "./types";

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
  channels: () => request<Channel[]>("/channels"),
  projects: () => request<Project[]>("/projects"),
  system: () => request<SystemStatus>("/system"),
  createChannel: (body: Record<string, unknown>) => request<Channel>("/channels", {method: "POST", body: JSON.stringify(body)}),
  createProject: (body: Record<string, unknown>) => request<Project>("/projects", {method: "POST", body: JSON.stringify(body)}),
  createPlan: (id: string) => request<Record<string, unknown>>(`/projects/${id}/plan`, {method: "POST"}),
};
