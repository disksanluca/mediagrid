import {invoke, isTauri} from "@tauri-apps/api/core";

export interface DesktopRuntime {
  api_port: number;
  data_dir: string;
}

export interface DesktopServices {
  core: boolean;
  worker: boolean;
  database: boolean;
  ollama: boolean;
  log_dir: string;
  error: string | null;
}

export function runningInDesktop(): boolean {
  return typeof window !== "undefined" && isTauri();
}

export async function desktopRuntime(): Promise<DesktopRuntime | null> {
  return runningInDesktop() ? invoke<DesktopRuntime>("desktop_runtime") : null;
}

export async function desktopServices(): Promise<DesktopServices | null> {
  return runningInDesktop() ? invoke<DesktopServices>("desktop_services") : null;
}

export async function desktopRestart(): Promise<DesktopRuntime> {
  return invoke<DesktopRuntime>("desktop_restart");
}

export async function desktopOpenLogs(): Promise<void> {
  return invoke<void>("desktop_open_logs");
}
