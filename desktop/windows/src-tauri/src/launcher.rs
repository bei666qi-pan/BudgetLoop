use std::{
    fs,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::Command,
    thread,
    time::{Duration, Instant},
};

pub const APPLICATION_SERVICES: [&str; 3] = ["control-plane", "worker", "web"];

pub fn validate_repository(path: &Path) -> Result<PathBuf, String> {
    let root = path
        .canonicalize()
        .map_err(|_| "所选文件夹不存在或无法访问。".to_owned())?;
    if root.join("docker-compose.yml").is_file() {
        Ok(root)
    } else {
        Err("请选择包含 docker-compose.yml 的 BudgetLoop 仓库目录。".to_owned())
    }
}

pub fn compose_up_args() -> Vec<&'static str> {
    vec![
        "compose",
        "up",
        "-d",
        "--build",
        APPLICATION_SERVICES[0],
        APPLICATION_SERVICES[1],
        APPLICATION_SERVICES[2],
    ]
}

pub fn first_valid_repository(candidates: impl IntoIterator<Item = PathBuf>) -> Option<PathBuf> {
    candidates
        .into_iter()
        .find_map(|candidate| validate_repository(&candidate).ok())
}

pub fn repository_candidates(saved: Option<PathBuf>) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(explicit) = std::env::var("BUDGETLOOP_REPO") {
        candidates.push(PathBuf::from(explicit));
    }
    if let Some(saved) = saved {
        candidates.push(saved);
    }
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.clone());
        if let Some(parent) = cwd.parent() {
            candidates.push(parent.to_path_buf());
        }
    }
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            candidates.push(parent.to_path_buf());
            if let Some(grandparent) = parent.parent() {
                candidates.push(grandparent.to_path_buf());
            }
        }
    }
    candidates
}

pub fn read_saved_repository(config_dir: &Path) -> Option<PathBuf> {
    let value = fs::read_to_string(config_dir.join("repository-path.txt")).ok()?;
    let value = value.trim();
    (!value.is_empty()).then(|| PathBuf::from(value))
}

pub fn save_repository(config_dir: &Path, repository: &Path) -> Result<(), String> {
    fs::create_dir_all(config_dir).map_err(|_| "无法创建 BudgetLoop 本地设置目录。".to_owned())?;
    fs::write(
        config_dir.join("repository-path.txt"),
        repository.display().to_string(),
    )
    .map_err(|_| "无法保存 BudgetLoop 仓库位置。".to_owned())
}

pub fn verify_docker() -> Result<(), String> {
    let status = Command::new("docker")
        .arg("info")
        .status()
        .map_err(|_| "找不到 Docker。请安装并启动 Docker Desktop 后重试。".to_owned())?;
    if status.success() {
        Ok(())
    } else {
        Err("Docker Desktop 尚未就绪。请启动它并等待引擎正常运行后重试。".to_owned())
    }
}

pub fn refresh_application_services(repository: &Path) -> Result<(), String> {
    let output = Command::new("docker")
        .args(compose_up_args())
        .current_dir(repository)
        .output()
        .map_err(|_| "无法启动 Docker Compose。请确认 Docker Desktop 已正常运行。".to_owned())?;
    if output.status.success() {
        Ok(())
    } else {
        Err("Docker Compose 未能重建 BudgetLoop 应用服务。请在仓库目录执行 `docker compose up -d --build control-plane worker web` 查看详细错误。".to_owned())
    }
}

pub fn wait_for_health(timeout: Duration) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if endpoint_responds("127.0.0.1:8000", "/api/health", false)
            && endpoint_responds("127.0.0.1:3001", "/api/status", false)
            && endpoint_responds("127.0.0.1:3000", "/", true)
        {
            return Ok(());
        }
        thread::sleep(Duration::from_secs(2));
    }
    Err(
        "BudgetLoop 服务在 180 秒内未通过健康检查。请在仓库目录执行 `docker compose logs` 排查。"
            .to_owned(),
    )
}

fn endpoint_responds(address: &str, path: &str, lax: bool) -> bool {
    let Ok(address) = address.parse::<SocketAddr>() else {
        return false;
    };
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_secs(2)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    if stream
        .write_all(format!("GET {path} HTTP/1.0\r\nHost: localhost\r\n\r\n").as_bytes())
        .is_err()
    {
        return false;
    }
    let mut response = [0_u8; 64];
    let Ok(length) = stream.read(&mut response) else {
        return false;
    };
    let first_line = String::from_utf8_lossy(&response[..length]);
    lax || first_line.starts_with("HTTP/1.0 2")
        || first_line.starts_with("HTTP/1.1 2")
        || first_line.starts_with("HTTP/1.1 3")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temporary_directory(name: &str) -> PathBuf {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("current time")
            .as_nanos();
        let path = std::env::temp_dir().join(format!("budgetloop-{name}-{suffix}"));
        fs::create_dir_all(&path).expect("create temporary directory");
        path
    }

    #[test]
    fn validates_only_budgetloop_repository_roots() {
        let invalid = temporary_directory("invalid");
        assert!(validate_repository(&invalid).is_err());

        let valid = temporary_directory("valid");
        fs::write(valid.join("docker-compose.yml"), "services: {}\n").expect("compose file");
        assert_eq!(
            validate_repository(&valid).expect("valid root"),
            valid.canonicalize().unwrap()
        );

        fs::remove_dir_all(invalid).ok();
        fs::remove_dir_all(valid).ok();
    }

    #[test]
    fn compose_refresh_is_limited_to_stateless_services() {
        assert_eq!(
            compose_up_args(),
            [
                "compose",
                "up",
                "-d",
                "--build",
                "control-plane",
                "worker",
                "web"
            ]
        );
    }
}
