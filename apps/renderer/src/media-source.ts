import {staticFile} from "remotion";

export function mediaSource(file: string): string {
  return /^(https?:|blob:|data:)/i.test(file) ? file : staticFile(file);
}
