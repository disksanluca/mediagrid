import {invoke, isTauri} from "@tauri-apps/api/core";
import {open} from "@tauri-apps/plugin-dialog";

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

export async function desktopStart(): Promise<DesktopRuntime> {
  return invoke<DesktopRuntime>("desktop_start");
}

export async function desktopStop(): Promise<void> {
  return invoke<void>("desktop_stop");
}

export async function desktopOpenLogs(): Promise<void> {
  return invoke<void>("desktop_open_logs");
}

export async function desktopChooseDataDir(): Promise<DesktopRuntime | null> {
  const selected = await open({directory: true, multiple: false, title: "Escolha uma pasta vazia para os dados MediaGrid"});
  return typeof selected === "string"
    ? invoke<DesktopRuntime>("desktop_set_data_dir", {selected})
    : null;
}
