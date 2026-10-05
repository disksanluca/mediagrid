#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod service_manager;

use service_manager::{DesktopRuntime, DesktopServices, DesktopState};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, RunEvent, State, WindowEvent};

#[tauri::command]
fn desktop_runtime(state: State<'_, DesktopState>) -> Result<DesktopRuntime, String> {
    let mut guard = state.processes.lock().map_err(|error| error.to_string())?;
    if let Some(processes) = guard.as_mut() {
        if processes.status().core {
            return Ok(processes.runtime());
        }
        return Err("MediaGrid Core is not responding. Open System to retry.".into());
    }
    let error = state.error.lock().map_err(|error| error.to_string())?;
    Err(error
        .clone()
        .unwrap_or_else(|| "MediaGrid is starting".into()))
}

#[tauri::command]
fn desktop_services(state: State<'_, DesktopState>) -> Result<DesktopServices, String> {
    let mut guard = state.processes.lock().map_err(|error| error.to_string())?;
    if let Some(processes) = guard.as_mut() {
        return Ok(processes.status());
    }
    let error = state.error.lock().map_err(|error| error.to_string())?;
    Ok(DesktopServices {
        core: false,
        worker: false,
        database: false,
        ollama: false,
        log_dir: String::new(),
        error: error.clone(),
    })
}

fn restart_services(app: tauri::AppHandle) -> Result<DesktopRuntime, String> {
    let state = app.state::<DesktopState>();
    let mut guard = state.processes.lock().map_err(|error| error.to_string())?;
    let port = guard.as_ref().map(|processes| processes.api_port);
    if let Some(mut processes) = guard.take() {
        processes.stop();
    }
    match service_manager::launch(&app, port) {
        Ok(processes) => {
            let runtime = processes.runtime();
            *guard = Some(processes);
            *state.error.lock().map_err(|error| error.to_string())? = None;
            Ok(runtime)
        }
        Err(error) => {
            *state
                .error
                .lock()
                .map_err(|lock_error| lock_error.to_string())? = Some(error.clone());
            Err(error)
        }
    }
}

#[tauri::command]
async fn desktop_restart(app: tauri::AppHandle) -> Result<DesktopRuntime, String> {
    tauri::async_runtime::spawn_blocking(move || restart_services(app))
        .await
        .map_err(|error| error.to_string())?
}

#[tauri::command]
fn desktop_open_logs(app: tauri::AppHandle) -> Result<(), String> {
    let log_dir = service_manager::default_data_dir(&app)?.join("Logs");
    std::fs::create_dir_all(&log_dir).map_err(|error| error.to_string())?;
    #[cfg(windows)]
    let program = "explorer.exe";
    #[cfg(not(windows))]
    let program = "xdg-open";
    std::process::Command::new(program)
        .arg(log_dir)
        .spawn()
        .map_err(|error| error.to_string())?;
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .manage(DesktopState::default())
        .invoke_handler(tauri::generate_handler![
            desktop_runtime,
            desktop_services,
            desktop_restart,
            desktop_open_logs
        ])
        .setup(|app| {
            let show = MenuItem::with_id(app, "show", "Abrir MediaGrid", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Sair do MediaGrid", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            let mut tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("MediaGrid")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.unminimize();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.build(app)?;
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let result = service_manager::launch(&handle, None);
                let state = handle.state::<DesktopState>();
                match result {
                    Ok(processes) => {
                        if let Ok(mut guard) = state.processes.lock() {
                            *guard = Some(processes);
                        }
                    }
                    Err(error) => {
                        if let Ok(mut guard) = state.error.lock() {
                            *guard = Some(error);
                        }
                    }
                }
                if let Some(main) = handle.get_webview_window("main") {
                    let _ = main.show();
                    let _ = main.set_focus();
                }
                if let Some(splash) = handle.get_webview_window("splash") {
                    let _ = splash.close();
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() != "main" {
                return;
            }
            match event {
                WindowEvent::CloseRequested { api, .. } => {
                    api.prevent_close();
                    let _ = window.hide();
                }
                WindowEvent::Resized(_) if window.is_minimized().unwrap_or(false) => {
                    let _ = window.hide();
                }
                _ => {}
            }
        })
        .build(tauri::generate_context!())
        .expect("failed to build MediaGrid desktop application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Ok(mut guard) = app.state::<DesktopState>().processes.lock() {
                    if let Some(mut processes) = guard.take() {
                        processes.stop();
                    }
                }
            }
        });
}
