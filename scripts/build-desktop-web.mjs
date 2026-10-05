import {spawnSync} from "node:child_process";
import {fileURLToPath} from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const next = path.join(root, "node_modules", "next", "dist", "bin", "next");
const result = spawnSync(process.execPath, [next, "build"], {
  cwd: path.join(root, "apps", "web"),
  env: {...process.env, MEDIAGRID_DESKTOP_BUILD: "1"},
  stdio: "inherit",
});
if (result.error) console.error(result.error);
process.exit(result.status ?? 1);
