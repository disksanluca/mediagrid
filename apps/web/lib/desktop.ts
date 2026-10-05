import {invoke, isTauri} from "@tauri-apps/api/core";
import {open, save} from "@tauri-apps/plugin-dialog";

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

export async function desktopCreateBackup(options: {assets: boolean; renders: boolean; models: boolean}): Promise<string | null> {
  const date = new Date().toISOString().slice(0, 10);
  const path = await save({title: "Salvar backup MediaGrid", defaultPath: `MediaGrid-${date}.mgrid`, filters: [{name: "Backup MediaGrid", extensions: ["mgrid"]}]});
  if (!path) return null;
  await invoke<void>("desktop_backup", {
    path,
    includeAssets: options.assets,
    includeRenders: options.renders,
    includeModels: options.models,
  });
  return path;
}

export async function desktopRestoreBackup(): Promise<string | null | undefined> {
  const path = await open({title: "Escolher backup MediaGrid", multiple: false, filters: [{name: "Backup MediaGrid", extensions: ["mgrid"]}]});
  if (typeof path !== "string") return undefined;
  return invoke<string | null>("desktop_restore", {path});
}
