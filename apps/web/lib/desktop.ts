import {invoke, isTauri} from "@tauri-apps/api/core";

export interface DesktopRuntime {
  api_port: number;
  data_dir: string;
}

export function runningInDesktop(): boolean {
  return typeof window !== "undefined" && isTauri();
}

export async function desktopRuntime(): Promise<DesktopRuntime | null> {
  return runningInDesktop() ? invoke<DesktopRuntime>("desktop_runtime") : null;
}
