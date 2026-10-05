import {spawnSync} from "node:child_process";
import {fileURLToPath} from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(npm, ["run", "build", "--workspace", "@mediagrid/web"], {
  cwd: root,
  env: {...process.env, MEDIAGRID_DESKTOP_BUILD: "1"},
  stdio: "inherit",
});
process.exit(result.status ?? 1);
