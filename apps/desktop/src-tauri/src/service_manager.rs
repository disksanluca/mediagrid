use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager};

#[derive(Serialize)]
pub struct DesktopRuntime {
    pub api_port: u16,
    pub data_dir: String,
}

#[derive(Serialize)]
pub struct DesktopServices {
    pub core: bool,
    pub worker: bool,
    pub database: bool,
    pub ollama: bool,
    pub log_dir: String,
    pub error: Option<String>,
}

pub struct Processes {
    api: Child,
    worker: Child,
    pub api_port: u16,
    pub data_dir: PathBuf,
    log_dir: PathBuf,
}

impl Processes {
    pub fn stop(&mut self) {
        stop_child(&mut self.worker);
        stop_child(&mut self.api);
    }

    pub fn status(&mut self) -> DesktopServices {
        let core = self
            .api
            .try_wait()
            .map(|status| status.is_none())
            .unwrap_or(false)
            && api_healthy(self.api_port);
        let worker = self
            .worker
            .try_wait()
            .map(|status| status.is_none())
            .unwrap_or(false);
        DesktopServices {
            core,
            worker,
            database: self
                .data_dir
                .join("Database")
                .join("mediagrid.db")
                .is_file(),
            ollama: TcpStream::connect_timeout(
                &SocketAddr::from(([127, 0, 0, 1], 11434)),
                Duration::from_millis(300),
            )
            .is_ok(),
            log_dir: self.log_dir.to_string_lossy().into_owned(),
            error: None,
        }
    }

    pub fn runtime(&self) -> DesktopRuntime {
        DesktopRuntime {
            api_port: self.api_port,
            data_dir: self.data_dir.to_string_lossy().into_owned(),
        }
    }
}

pub struct DesktopState {
    pub processes: Mutex<Option<Processes>>,
    pub error: Mutex<Option<String>>,
}

#[derive(Serialize, Deserialize)]
struct Preferences {
    data_dir: PathBuf,
}

fn preferences_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(app
        .path()
        .app_config_dir()
        .map_err(|error| error.to_string())?
        .join("desktop.json"))
}

fn saved_data_dir(app: &AppHandle) -> Result<Option<PathBuf>, String> {
    let path = preferences_path(app)?;
    if !path.is_file() {
        return Ok(None);
    }
    let content = fs::read(&path).map_err(|error| error.to_string())?;
    let preferences: Preferences =
        serde_json::from_slice(&content).map_err(|error| error.to_string())?;
    Ok(Some(preferences.data_dir))
}

fn save_data_dir(app: &AppHandle, path: &Path) -> Result<(), String> {
    let preferences = preferences_path(app)?;
    fs::create_dir_all(preferences.parent().ok_or("Missing config directory")?)
        .map_err(|error| error.to_string())?;
    let temporary = preferences.with_extension("tmp");
    fs::write(
        &temporary,
        serde_json::to_vec_pretty(&Preferences {
            data_dir: path.to_path_buf(),
        })
        .map_err(|error| error.to_string())?,
    )
    .map_err(|error| error.to_string())?;
    if preferences.is_file() {
        fs::remove_file(&preferences).map_err(|error| error.to_string())?;
    }
    fs::rename(temporary, preferences).map_err(|error| error.to_string())
}

impl Default for DesktopState {
    fn default() -> Self {
        Self {
            processes: Mutex::new(None),
            error: Mutex::new(None),
        }
    }
}

pub fn default_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    if let Some(saved) = saved_data_dir(app)? {
        return Ok(saved);
    }
    let base = match std::env::var_os("LOCALAPPDATA") {
        Some(path) => PathBuf::from(path),
        None => app
            .path()
            .app_local_data_dir()
            .map_err(|error| error.to_string())?,
    };
    Ok(base.join("MediaGrid").join("Data"))
}

fn copy_tree(source: &Path, target: &Path) -> Result<(), String> {
    if !source.is_dir() {
        return Ok(());
    }
    fs::create_dir_all(target).map_err(|error| error.to_string())?;
    for entry in fs::read_dir(source).map_err(|error| error.to_string())? {
        let entry = entry.map_err(|error| error.to_string())?;
        let destination = target.join(entry.file_name());
        if entry
            .file_type()
            .map_err(|error| error.to_string())?
            .is_dir()
        {
            copy_tree(&entry.path(), &destination)?;
        } else {
            fs::copy(entry.path(), destination).map_err(|error| error.to_string())?;
        }
    }
    Ok(())
}

pub fn relocate_data_dir(app: &AppHandle, selected: &Path) -> Result<PathBuf, String> {
    let previous = default_data_dir(app)?;
    fs::create_dir_all(selected).map_err(|error| error.to_string())?;
    let selected = selected.canonicalize().map_err(|error| error.to_string())?;
    let previous = previous.canonicalize().map_err(|error| error.to_string())?;
    if selected == previous {
        return Ok(selected);
    }
    if selected.starts_with(&previous) || previous.starts_with(&selected) {
        return Err(
            "Choose a separate data folder, not a parent or child of the current folder".into(),
        );
    }
    if fs::read_dir(&selected)
        .map_err(|error| error.to_string())?
        .next()
        .is_some()
    {
        return Err("The selected data folder must be empty to avoid overwriting files".into());
    }
    copy_tree(&previous, &selected)?;
    save_data_dir(app, &selected)?;
    Ok(selected)
}

pub fn restore_data_dir(app: &AppHandle, previous: &Path) -> Result<(), String> {
    save_data_dir(app, previous)
}

fn free_port() -> Result<u16, String> {
    let listener = TcpListener::bind(("127.0.0.1", 0)).map_err(|error| error.to_string())?;
    let port = listener
        .local_addr()
        .map_err(|error| error.to_string())?
        .port();
    drop(listener);
    Ok(port)
}

fn api_healthy(port: u16) -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(500)) else {
        return false;
    };
    if stream
        .set_read_timeout(Some(Duration::from_millis(500)))
        .is_err()
    {
        return false;
    }
    if stream
        .write_all(
            b"GET /api/v1/system/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n",
        )
        .is_err()
    {
        return false;
    }
    let mut head = [0u8; 12];
    stream.read_exact(&mut head).is_ok() && &head == b"HTTP/1.1 200"
}

fn project_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(3)
        .expect("desktop crate must be inside apps/desktop/src-tauri")
        .to_path_buf()
}

fn service_command(
    app: &AppHandle,
    service: &str,
    port: u16,
    data_dir: &Path,
) -> Result<Command, String> {
    let mut command = if cfg!(debug_assertions) {
        let mut command = Command::new("uv");
        command.current_dir(project_root());
        command.args(["run", "python", "-m", "scripts.desktop_service", service]);
        command
    } else {
        let parent = std::env::current_exe()
            .map_err(|error| error.to_string())?
            .parent()
            .ok_or("Cannot locate MediaGrid executable directory")?
            .to_path_buf();
        let sidecar = parent.join("mediagrid-service.exe");
        if !sidecar.is_file() {
            return Err(format!(
                "Missing local service binary: {}",
                sidecar.display()
            ));
        }
        let mut command = Command::new(sidecar);
        command.arg(service);
        command
    };
    if service == "api" {
        command.args(["--port", &port.to_string()]);
    }
    let database = data_dir.join("Database").join("mediagrid.db");
    let database_url = format!(
        "sqlite:///{}",
        database.to_string_lossy().replace('\\', "/")
    );
    command.env("MEDIAGRID_MODE", "LOCAL");
    command.env("ALLOW_PAID_AI", "false");
    command.env("DRY_RUN", "true");
    command.env("MEDIAGRID_DATA_DIR", data_dir);
    command.env("DATABASE_URL", database_url);
    if !cfg!(debug_assertions) {
        let runtime = app
            .path()
            .resource_dir()
            .map_err(|error| error.to_string())?
            .join("runtime");
        let node = runtime.join("node.exe");
        let renderer = runtime.join("renderer");
        let renderer_entry = renderer.join("src").join("index.ts");
        let ffmpeg = runtime.join("bin").join("ffmpeg.exe");
        let ffprobe = runtime.join("bin").join("ffprobe.exe");
        let browser_relative = fs::read_to_string(runtime.join("browser-path.txt"))
            .map_err(|error| format!("Missing local renderer browser path: {error}"))?;
        let browser = renderer.join(browser_relative.trim());
        for required in [&node, &renderer_entry, &ffmpeg, &ffprobe, &browser] {
            if !required.is_file() {
                return Err(format!(
                    "Missing desktop runtime file: {}",
                    required.display()
                ));
            }
        }
        command.env("MEDIAGRID_NODE_PATH", node);
        command.env("MEDIAGRID_RENDERER_ROOT", renderer);
        command.env("MEDIAGRID_FFMPEG_PATH", ffmpeg);
        command.env("MEDIAGRID_FFPROBE_PATH", ffprobe);
        command.env("MEDIAGRID_BROWSER_PATH", browser);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    Ok(command)
}

fn spawn_logged(mut command: Command, log: &Path) -> Result<Child, String> {
    let output = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log)
        .map_err(|error| error.to_string())?;
    let errors = output.try_clone().map_err(|error| error.to_string())?;
    command.stdout(Stdio::from(output));
    command.stderr(Stdio::from(errors));
    command.spawn().map_err(|error| error.to_string())
}

pub fn launch(app: &AppHandle, preferred_port: Option<u16>) -> Result<Processes, String> {
    let data_dir = default_data_dir(app)?;
    fs::create_dir_all(data_dir.join("Database")).map_err(|error| error.to_string())?;
    let log_dir = data_dir.join("Logs");
    fs::create_dir_all(&log_dir).map_err(|error| error.to_string())?;
    let port = preferred_port.unwrap_or(free_port()?);
    let mut api = spawn_logged(
        service_command(app, "api", port, &data_dir)?,
        &log_dir.join("core.log"),
    )?;
    let deadline = Instant::now() + Duration::from_secs(45);
    while Instant::now() < deadline {
        if api_healthy(port) {
            let worker = match spawn_logged(
                service_command(app, "worker", port, &data_dir)?,
                &log_dir.join("worker.log"),
            ) {
                Ok(worker) => worker,
                Err(error) => {
                    stop_child(&mut api);
                    return Err(error);
                }
            };
            return Ok(Processes {
                api,
                worker,
                api_port: port,
                data_dir,
                log_dir,
            });
        }
        if api.try_wait().map_err(|error| error.to_string())?.is_some() {
            return Err(format!(
                "MediaGrid Core stopped during startup. See {}",
                log_dir.join("core.log").display()
            ));
        }
        thread::sleep(Duration::from_millis(250));
    }
    stop_child(&mut api);
    Err(format!(
        "MediaGrid Core did not start in 45 seconds. See {}",
        log_dir.join("core.log").display()
    ))
}

fn stop_child(child: &mut Child) {
    if child.try_wait().is_ok_and(|status| status.is_some()) {
        return;
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let _ = Command::new("taskkill")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(0x08000000)
            .status();
    }
    #[cfg(not(windows))]
    let _ = child.kill();
    let _ = child.wait();
}
