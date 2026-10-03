import {spawn} from "node:child_process";
import {mkdir, writeFile} from "node:fs/promises";
import process from "node:process";

const target = process.argv[2] ?? "http://127.0.0.1:3000";
const output = process.argv[3] ?? "data/previews/panel.png";
const port = 9223;
await mkdir("/tmp/mediagrid-preview-profile", {recursive: true});
await mkdir("/tmp/mediagrid-preview-cache", {recursive: true});
await mkdir(new URL(".", `file://${process.cwd()}/${output}`).pathname, {recursive: true});

const browser = spawn("/usr/bin/chromium", [
  "--headless=new",
  "--no-sandbox",
  "--disable-gpu",
  "--disable-dev-shm-usage",
  "--disable-crash-reporter",
  `--remote-debugging-port=${port}`,
  "--remote-debugging-address=127.0.0.1",
  "--user-data-dir=/tmp/mediagrid-preview-profile",
  "about:blank",
], {
  env: {
    ...process.env,
    XDG_CACHE_HOME: "/tmp/mediagrid-preview-cache",
    XDG_CONFIG_HOME: "/tmp/mediagrid-preview-cache",
  },
  stdio: "ignore",
});

try {
  let version;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) {
        version = await response.json();
        break;
      }
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  if (!version) throw new Error("Chromium DevTools did not start");

  const tabResponse = await fetch(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent(target)}`,
    {method: "PUT"},
  );
  const tab = await tabResponse.json();
  const socket = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, {once: true});
    socket.addEventListener("error", reject, {once: true});
  });

  let id = 0;
  const pending = new Map();
  socket.addEventListener("message", ({data}) => {
    const message = JSON.parse(data);
    if (!message.id || !pending.has(message.id)) return;
    const {resolve, reject} = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });
  const command = (method, params = {}) => new Promise((resolve, reject) => {
    id += 1;
    pending.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, method, params}));
  });

  await command("Page.enable");
  await command("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await command("Page.navigate", {url: target});
  await new Promise((resolve) => setTimeout(resolve, 3000));
  const screenshot = await command("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
  });
  await writeFile(output, Buffer.from(screenshot.data, "base64"));
  socket.close();
} finally {
  browser.kill("SIGTERM");
}
