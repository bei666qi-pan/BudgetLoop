#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{path::PathBuf, time::Duration};

use budgetloop_windows_launcher::launcher;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_dialog::DialogExt;

fn config_directory(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_config_dir()
        .map_err(|_| "无法定位 BudgetLoop 本地设置目录。".to_owned())
}

fn status(app: &AppHandle, message: &str) {
    let _ = app.emit("launcher-status", message);
}

fn start_application(app: AppHandle, repository: PathBuf) -> Result<(), String> {
    let config_dir = config_directory(&app)?;
    launcher::save_repository(&config_dir, &repository)?;
    status(&app, "正在检查 Docker Desktop…");
    launcher::verify_docker()?;
    status(&app, "正在刷新本地应用代码…");
    launcher::refresh_application_services(&repository)?;
    status(&app, "正在等待 BudgetLoop 服务就绪…");
    launcher::wait_for_health(Duration::from_secs(180))?;
    status(&app, "服务已就绪，正在打开 BudgetLoop…");
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "启动窗口不可用。".to_owned())?;
    window
        .navigate(
            "http://localhost:3000"
                .parse()
                .map_err(|_| "本地地址无效。".to_owned())?,
        )
        .map_err(|_| "无法打开本地 BudgetLoop 页面。".to_owned())
}

#[tauri::command]
async fn select_repository(app: AppHandle) -> Result<(), String> {
    let dialog_app = app.clone();
    let choice = tauri::async_runtime::spawn_blocking(move || {
        dialog_app.dialog().file().blocking_pick_folder()
    })
    .await
    .map_err(|_| "无法显示文件夹选择器。".to_owned())?;
    let repository = choice
        .ok_or_else(|| "未选择 BudgetLoop 仓库。".to_owned())?
        .into_path()
        .map_err(|_| "所选位置不是可用的本地文件夹。".to_owned())?;
    let repository = launcher::validate_repository(&repository)?;
    let start_app = app.clone();
    tauri::async_runtime::spawn_blocking(move || start_application(start_app, repository))
        .await
        .map_err(|_| "启动器任务意外终止。".to_owned())?
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![select_repository])
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn_blocking(move || {
                let saved = config_directory(&handle)
                    .ok()
                    .and_then(|directory| launcher::read_saved_repository(&directory));
                let Some(repository) =
                    launcher::first_valid_repository(launcher::repository_candidates(saved))
                else {
                    status(
                        &handle,
                        "请选择包含 docker-compose.yml 的 BudgetLoop 仓库目录。",
                    );
                    return;
                };
                if let Err(error) = start_application(handle.clone(), repository) {
                    status(&handle, &error);
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("BudgetLoop launcher failed to run");
}
