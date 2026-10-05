use serde::Serialize;
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

impl Default for DesktopState {
    fn default() -> Self {
        Self {
            processes: Mutex::new(None),
            error: Mutex::new(None),
        }
    }
}

pub fn default_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let base = match std::env::var_os("LOCALAPPDATA") {
        Some(path) => PathBuf::from(path),
        None => app
            .path()
            .app_local_data_dir()
            .map_err(|error| error.to_string())?,
    };
    Ok(base.join("MediaGrid").join("Data"))
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

fn service_command(service: &str, port: u16, data_dir: &Path) -> Result<Command, String> {
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
        service_command("api", port, &data_dir)?,
        &log_dir.join("core.log"),
    )?;
    let deadline = Instant::now() + Duration::from_secs(45);
    while Instant::now() < deadline {
        if api_healthy(port) {
            let worker = match spawn_logged(
                service_command("worker", port, &data_dir)?,
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
