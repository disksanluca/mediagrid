import {api, type UploadState} from "./api";

const CHUNK_BYTES = 8 * 1024 * 1024;

export async function uploadLongVideo(
  file: File,
  rights: {rights_status:string;creator:string|null;source_url:string|null;license_name:string|null;commercial_use:boolean},
  onProgress: (state: UploadState) => void,
): Promise<{asset_id:string;proxy_job_id:string|null}> {
  const key = `mediagrid-upload:${file.name}:${file.size}:${file.lastModified}`;
  let state: UploadState | null = null;
  const savedId = window.localStorage.getItem(key);
  if (savedId) {
    try {
      state = await api.uploadState(savedId);
    } catch {
      window.localStorage.removeItem(key);
    }
  }
  if (state && (
    state.rights_status !== rights.rights_status || state.creator !== rights.creator ||
    state.source_url !== rights.source_url || state.license_name !== rights.license_name ||
    state.commercial_use !== rights.commercial_use
  )) {
    throw new Error("Para retomar, use os mesmos dados de direitos da primeira tentativa.");
  }
  if (state?.status === "FAILED") {
    window.localStorage.removeItem(key);
    throw new Error(state.error ?? "A importação anterior falhou. Tente novamente.");
  }
  if (state?.status === "COMPLETE") {
    window.localStorage.removeItem(key);
    return {asset_id:state.asset_id!, proxy_job_id:null};
  }
  if (!state) {
    state = await api.createUpload({
      name:file.name, media_type:"video/mp4", size_bytes:file.size, ...rights,
    });
    window.localStorage.setItem(key,state.id);
  }
  onProgress(state);
  while (state.received_bytes < file.size) {
    const offset = state.received_bytes;
    state = await api.uploadChunk(state.id, offset, file.slice(offset, offset + CHUNK_BYTES));
    onProgress(state);
  }
  const completed = await api.completeUpload(state.id);
  window.localStorage.removeItem(key);
  onProgress(completed.upload);
  return completed;
}
