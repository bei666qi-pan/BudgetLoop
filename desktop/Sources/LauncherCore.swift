import Foundation
import Security

// MARK: - State machine (design D5)

enum LauncherState {
    case checkingDocker
    case startingDocker
    case materializingEnv
    case startingStack
    case waitingHealth
    case ready
    case running
    case failed(step: String, message: String, remedy: String)
}

protocol LauncherDelegate: AnyObject {
    func launcherStatus(_ text: String)
    func launcherReady(adopted: Bool, gatewayConfigured: Bool)
    func launcherFailed(step: String, message: String, remedy: String)
}

enum LauncherError: LocalizedError {
    case envExampleMissing

    var errorDescription: String? {
        switch self {
        case .envExampleMissing:
            return "仓库中既没有 .env，也找不到 .env.example，无法生成环境配置。"
        }
    }
}

// MARK: - Logging

final class LauncherLog {
    static let shared = LauncherLog()
    private let url: URL
    private let formatter = ISO8601DateFormatter()

    private init() {
        let dir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        url = dir.appendingPathComponent("BudgetLoop-launcher.log")
    }

    func write(_ message: String) {
        let line = "[\(formatter.string(from: Date()))] \(message)\n"
        NSLog("BudgetLoop: %@", message)
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        if let handle = try? FileHandle(forWritingTo: url) {
            handle.seekToEndOfFile()
            handle.write(Data(line.utf8))
            try? handle.close()
        }
    }
}

func log(_ message: String) { LauncherLog.shared.write(message) }

// MARK: - Process helpers

struct ProcessResult {
    let status: Int32
    let output: String
    let timedOut: Bool
}

/// Runs a process synchronously, merging stdout+stderr, with a timeout.
@discardableResult
func runSync(_ launchPath: String,
             _ args: [String],
             cwd: URL? = nil,
             extraEnv: [String: String]? = nil,
             timeout: TimeInterval = 30) -> ProcessResult {
    let proc = Process()
    proc.executableURL = URL(fileURLWithPath: launchPath)
    proc.arguments = args
    if let cwd = cwd { proc.currentDirectoryURL = cwd }

    var env = ProcessInfo.processInfo.environment
    let basePath = env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin"
    if !basePath.contains("/usr/local/bin") {
        env["PATH"] = basePath + ":/usr/local/bin:/opt/homebrew/bin"
    }
    if let extraEnv = extraEnv { env.merge(extraEnv) { _, new in new } }
    proc.environment = env

    let pipe = Pipe()
    proc.standardOutput = pipe
    proc.standardError = pipe

    let lock = NSLock()
    var collected = Data()
    pipe.fileHandleForReading.readabilityHandler = { handle in
        let chunk = handle.availableData
        if !chunk.isEmpty {
            lock.lock()
            collected.append(chunk)
            lock.unlock()
        }
    }

    do {
        try proc.run()
    } catch {
        pipe.fileHandleForReading.readabilityHandler = nil
        return ProcessResult(status: -1, output: error.localizedDescription, timedOut: false)
    }

    let deadline = Date().addingTimeInterval(timeout)
    while proc.isRunning && Date() < deadline {
        Thread.sleep(forTimeInterval: 0.05)
    }
    var timedOut = false
    if proc.isRunning {
        timedOut = true
        proc.terminate()
    }
    proc.waitUntilExit()
    pipe.fileHandleForReading.readabilityHandler = nil
    collected.append(pipe.fileHandleForReading.readDataToEndOfFile())

    let output = String(data: collected, encoding: .utf8) ?? ""
    return ProcessResult(status: timedOut ? -2 : proc.terminationStatus,
                         output: output,
                         timedOut: timedOut)
}

// MARK: - LauncherCore

final class LauncherCore {
    weak var delegate: LauncherDelegate?

    /// Keychain service constant, mirrors KEYCHAIN_SERVICE in
    /// backend/app/ai_gateway/local_settings.py.
    private let keychainService = "BudgetLoop AI Gateway API Key"
    private let agentServerImage = "ghcr.io/openhands/agent-server:latest-python"
    private let webURL = "http://localhost:3000"

    /// lax=true 表示只要服务器应答了 HTTP 即视为存活（web 根路径可能返回
    /// 应用级错误页，如 dev server 的 500，但服务本身是健康的）；API 健康
    /// 端点保持严格（2xx/3xx）。
    private let healthChecks: [(name: String, url: String, port: Int, lax: Bool)] = [
        ("control-plane", "http://localhost:8000/api/health", 8000, false),
        ("new-api", "http://localhost:3001/api/status", 3001, false),
        ("web", "http://localhost:3000", 3000, true),
    ]

    private var state: LauncherState = .checkingDocker
    private var repoRoot = URL(fileURLWithPath: "/")
    private var dockerPath: String?
    private var composeEnv: [String: String] = [:]
    private var adopted = false
    private var startedByApp = false
    private var gatewayConfigured = false

    /// True when the app itself brought the stack up and must stop it on exit.
    private(set) var needsTeardown = false

    func start() {
        DispatchQueue.global(qos: .userInitiated).async { self.run() }
    }

    /// Stops app-started compose services (never adopted ones), then calls back.
    func teardown(completion: @escaping () -> Void) {
        DispatchQueue.global(qos: .utility).async {
            if self.needsTeardown, let docker = self.dockerPath {
                log("正在停止应用启动的 compose 服务…")
                let result = runSync(docker, ["compose", "stop"],
                                     cwd: self.repoRoot,
                                     extraEnv: self.composeEnv,
                                     timeout: 120)
                log("docker compose stop 退出码 \(result.status)")
            }
            completion()
        }
    }

    /// Recreate only the stateless gateway consumers after the foreground
    /// settings page has safely changed the host-local configuration. Data
    /// services are deliberately left untouched.
    func applySavedGatewaySettings(completion: @escaping (Bool, String?) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async {
            guard let docker = self.dockerPath else {
                completion(false, "本机服务尚未就绪，请稍后重试。")
                return
            }
            guard let gatewayEnv = self.bootstrapGateway() else {
                completion(false, "已保存设置，但 macOS Keychain 暂时不可用。请重新打开 BudgetLoop 后重试。")
                return
            }
            self.buildComposeEnv(gatewayEnv: gatewayEnv)
            self.status("正在应用已保存的 AI 网关配置…")
            let result = runSync(
                docker,
                ["compose", "up", "-d", "--force-recreate", "control-plane", "worker"],
                cwd: self.repoRoot,
                extraEnv: self.composeEnv,
                timeout: 300
            )
            guard result.status == 0 else {
                let tail = String(self.redactedComposeOutput(result.output).suffix(500))
                completion(false, "设置已保存，但服务暂未能应用：\(tail)")
                return
            }
            self.gatewayConfigured = true
            log("已应用前台保存的 AI 网关配置")
            completion(true, nil)
        }
    }

    // MARK: State machine driver

    private func run() {
        repoRoot = resolveRepoRoot()
        log("仓库目录：\(repoRoot.path)")

        // 1. checkingDocker
        state = .checkingDocker
        status("正在检查 Docker…")
        guard let docker = findDockerCLI() else {
            fail(step: "检查 Docker",
                 message: "未找到 docker 命令行工具。BudgetLoop 依赖 Docker Desktop 运行本地服务。",
                 remedy: "请先安装 Docker Desktop（https://www.docker.com/products/docker-desktop/），安装后重新打开 BudgetLoop。")
            return
        }
        dockerPath = docker

        // 2. startingDocker (only if the daemon is down)
        if !dockerDaemonUp() {
            state = .startingDocker
            guard FileManager.default.fileExists(atPath: "/Applications/Docker.app") else {
                fail(step: "启动 Docker Desktop",
                     message: "Docker 已安装但未运行，且在 /Applications 下找不到 Docker.app。",
                     remedy: "请手动安装或启动 Docker Desktop，待其就绪后重新打开 BudgetLoop。")
                return
            }
            status("正在启动 Docker Desktop…（最长等待 120 秒）")
            runSync("/usr/bin/open", ["-a", "Docker"], timeout: 10)
            let deadline = Date().addingTimeInterval(120)
            var up = false
            while Date() < deadline {
                if dockerDaemonUp() { up = true; break }
                Thread.sleep(forTimeInterval: 2)
            }
            guard up else {
                fail(step: "启动 Docker Desktop",
                     message: "Docker Desktop 在 120 秒内未能就绪。",
                     remedy: "请手动打开 Docker Desktop，确认状态栏图标显示正常运行后重试。")
                return
            }
        }
        log("Docker 守护进程正常")

        // 3. materializingEnv
        state = .materializingEnv
        status("正在准备环境配置（.env）…")
        do {
            try materializeEnvIfNeeded()
        } catch {
            fail(step: "准备环境配置",
                 message: error.localizedDescription,
                 remedy: "请检查仓库目录 \(repoRoot.path) 的读写权限，或参照 .env.example 手动创建 .env。")
            return
        }

        // 4. startingStack（adopt-mode: 健康栈已在运行则直接接管）
        state = .startingStack
        status("正在检查是否已有运行中的 BudgetLoop 服务…")
        // Gateway bootstrap (local settings + Keychain) is prepared before the
        // adopt check. In adopt mode it remains read-only; in app-start mode the
        // values are supplied solely to the compose child process.
        let gatewayEnv = bootstrapGateway()
        gatewayConfigured = gatewayEnv != nil
        buildComposeEnv(gatewayEnv: gatewayEnv)
        let stackAlreadyHealthy = httpOK("http://localhost:8000/api/health") && httpOK(webURL, lax: true)
        if stackAlreadyHealthy && !gatewayServicesNeedRefresh(gatewayEnv) {
            adopted = true
            log("检测到健康的运行中服务栈，进入接管（adopt）模式")
            status("检测到已在运行的 BudgetLoop 服务，直接接管…")
        } else if stackAlreadyHealthy {
            // The app did not start this stack, but it can safely refresh only
            // the two stateless services that consume the new ephemeral
            // Keychain-derived gateway environment.  Keep all data services
            // running and never mark the adopted stack for teardown.
            adopted = true
            status("正在将已保存的 AI 网关配置应用到控制面…")
            let result = runSync(docker,
                                 ["compose", "up", "-d", "--force-recreate", "control-plane", "worker"],
                                 cwd: repoRoot,
                                 extraEnv: composeEnv,
                                 timeout: 300)
            guard result.status == 0 else {
                let tail = String(redactedComposeOutput(result.output).suffix(800))
                fail(step: "应用 AI 网关配置",
                     message: "无法刷新控制面（退出码 \(result.status)）。\n\(tail)",
                     remedy: "请确认 Docker Desktop 正常运行后重试；不会修改已保存的网关地址或密钥。")
                return
            }
            log("已刷新 control-plane 与 worker 的临时网关环境")
        } else {
            // Port-conflict detection before compose up.
            for check in healthChecks where portBound(check.port) && !httpOK(check.url, lax: check.lax) {
                fail(step: "启动服务栈",
                     message: "端口 \(check.port) 已被其他进程占用，且 BudgetLoop 的 \(check.name) 健康检查未通过。",
                     remedy: "在终端运行 `lsof -i :\(check.port)` 找到占用进程并停止它，然后重新打开 BudgetLoop。")
                return
            }

            status("正在启动 BudgetLoop 服务（docker compose up，首次运行可能需要构建镜像）…")
            startAgentImagePull() // 非阻塞，与 compose up 并行
            let result = runSync(docker,
                                 ["compose", "up", "-d",
                                  "postgres", "valkey", "new-api",
                                  "control-plane", "worker", "web"],
                                 cwd: repoRoot,
                                 extraEnv: composeEnv,
                                 timeout: 900)
            guard result.status == 0 else {
                let tail = String(redactedComposeOutput(result.output).suffix(800))
                fail(step: "启动服务栈",
                     message: "docker compose up 失败（退出码 \(result.status)）。\n\(tail)",
                     remedy: "在仓库目录运行 `docker compose logs` 查看详细错误后重试。")
                return
            }
            startedByApp = true
            needsTeardown = true
            log("compose 服务已由应用启动")
        }

        // 5. waitingHealth
        state = .waitingHealth
        for check in healthChecks {
            status("正在等待 \(check.name) 通过健康检查…")
            let deadline = Date().addingTimeInterval(180)
            var ok = false
            while Date() < deadline {
                if httpOK(check.url, timeout: 5, lax: check.lax) { ok = true; break }
                Thread.sleep(forTimeInterval: 2)
            }
            guard ok else {
                fail(step: "等待健康检查",
                     message: "\(check.name)（\(check.url)）在 180 秒内未就绪。",
                     remedy: adopted
                        ? "请检查正在运行的 \(check.name) 服务日志，或稍后重新打开 BudgetLoop。"
                        : "在仓库目录运行 `docker compose logs \(check.name)` 排查错误后重试。")
                return
            }
        }

        // 6. ready → running(window)（由 AppDelegate 展示窗口）
        state = .ready
        log("全部服务就绪，打开主窗口")
        delegate?.launcherReady(adopted: adopted, gatewayConfigured: gatewayConfigured)
        state = .running
    }

    // MARK: Repo root resolution

    /// 默认取 App 包的相对位置（desktop/BudgetLoop.app → ../..，即向上找含
    /// docker-compose.yml 的目录；拷到仓库根部的 BudgetLoop.app 同样适用），
    /// 可用 BUDGETLOOP_REPO 环境变量覆盖。
    private func resolveRepoRoot() -> URL {
        if let override = ProcessInfo.processInfo.environment["BUDGETLOOP_REPO"],
           !override.isEmpty {
            return URL(fileURLWithPath: (override as NSString).expandingTildeInPath)
        }
        let bundleURL = Bundle.main.bundleURL
        let parent = bundleURL.deletingLastPathComponent()
        let grandparent = parent.deletingLastPathComponent()
        for candidate in [parent, grandparent] {
            let composeFile = candidate.appendingPathComponent("docker-compose.yml")
            if FileManager.default.fileExists(atPath: composeFile.path) {
                return candidate
            }
        }
        return grandparent
    }

    // MARK: Docker helpers

    private func findDockerCLI() -> String? {
        let candidates = ["/usr/local/bin/docker", "/opt/homebrew/bin/docker", "/usr/bin/docker"]
        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            return path
        }
        for dir in (ProcessInfo.processInfo.environment["PATH"] ?? "").split(separator: ":") {
            let path = "\(dir)/docker"
            if FileManager.default.isExecutableFile(atPath: path) { return path }
        }
        return nil
    }

    private func dockerDaemonUp() -> Bool {
        guard let docker = dockerPath else { return false }
        return runSync(docker, ["info"], timeout: 15).status == 0
    }

    /// 与 compose up 并行预拉 agent-server 镜像（worker 派生工作区容器用）。
    private func startAgentImagePull() {
        guard let docker = dockerPath else { return }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: docker)
        proc.arguments = ["pull", agentServerImage]
        proc.currentDirectoryURL = repoRoot
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = (env["PATH"] ?? "/usr/bin:/bin") + ":/usr/local/bin:/opt/homebrew/bin"
        proc.environment = env
        proc.terminationHandler = { p in
            log("agent-server 镜像拉取结束（退出码 \(p.terminationStatus)）")
        }
        do {
            try proc.run()
            log("已并行开始拉取 \(agentServerImage)")
        } catch {
            log("agent-server 镜像拉取启动失败：\(error.localizedDescription)")
        }
    }

    // MARK: .env materialization

    /// 仅当 .env 不存在时从 .env.example 生成；绝不覆盖已有 .env。
    private func materializeEnvIfNeeded() throws {
        let envURL = repoRoot.appendingPathComponent(".env")
        if FileManager.default.fileExists(atPath: envURL.path) {
            log(".env 已存在，跳过生成")
            return
        }
        let exampleURL = repoRoot.appendingPathComponent(".env.example")
        guard FileManager.default.fileExists(atPath: exampleURL.path) else {
            throw LauncherError.envExampleMissing
        }
        var text = try String(contentsOf: exampleURL, encoding: .utf8)
        let apiToken = randomHex(32)
        let generated: [(String, String)] = [
            ("NEW_API_SESSION_SECRET", randomHex(32)),
            ("POSTGRES_PASSWORD", randomHex(24)),
            ("MINIO_SECRET_KEY", randomHex(24)),
            ("API_TOKEN", apiToken),
            // The web bundle must use the same token as the control plane.
            ("NEXT_PUBLIC_API_TOKEN", apiToken),
        ]
        for (key, value) in generated {
            text = upsertEnvValue(text, key: key, value: value)
        }
        try text.write(to: envURL, atomically: true, encoding: .utf8)
        log("已从 .env.example 生成新的 .env（含随机密钥）")
    }

    private func upsertEnvValue(_ text: String, key: String, value: String) -> String {
        var lines = text.components(separatedBy: .newlines)
        var replaced = false
        for i in lines.indices where lines[i].trimmingCharacters(in: .whitespaces).hasPrefix("\(key)=") {
            lines[i] = "\(key)=\(value)"
            replaced = true
        }
        if !replaced {
            if lines.last == "" {
                lines.insert("\(key)=\(value)", at: lines.count - 1)
            } else {
                lines.append("\(key)=\(value)")
            }
        }
        return lines.joined(separator: "\n")
    }

    private func buildComposeEnv(gatewayEnv: [String: String]?) {
        // Compose owns parsing .env. Managed-device security software can
        // block native app reads of dotfiles, so the launcher only supplies
        // the ephemeral Keychain-derived gateway overlay here.
        var env: [String: String] = [:]
        if let gatewayEnv = gatewayEnv {
            env.merge(gatewayEnv) { _, new in new }
        }
        composeEnv = env
    }

    // MARK: Gateway bootstrap (local settings + Keychain)

    /// 读取 ~/Library/Application Support/BudgetLoop/ai-gateway.json 及 Keychain
    /// 中的 API Key；成功时返回注入 compose 进程环境的 AI_GATEWAY_* 变量
    /// （不写入磁盘上的 .env），失败时返回 nil 走引导配置流程。
    private func bootstrapGateway() -> [String: String]? {
        let settingsURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/BudgetLoop/ai-gateway.json")
        guard let data = try? Data(contentsOf: settingsURL),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            log("未找到本地网关配置 ai-gateway.json")
            return nil
        }
        let baseURL = (obj["base_url"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let kind = obj["kind"] as? String ?? "compatible"
        let recommendationModel = obj["recommendation_model"] as? String ?? ""
        let defaultModel = obj["default_model"] as? String ?? ""
        guard !baseURL.isEmpty else {
            log("本地网关配置缺少 base_url")
            return nil
        }
        guard let apiKey = NativeGatewaySettingsStore.readSecret(service: keychainService) else {
            log("Keychain 凭据读取失败或为空")
            return nil
        }
        log("已从本地设置 + Keychain 加载 compatible 网关配置")
        var gateway: [String: String] = [
            "AI_GATEWAY_TYPE": kind,
            "AI_GATEWAY_BASE_URL": baseURL,
            "AI_GATEWAY_API_KEY": apiKey,
            "AI_GATEWAY_RECOMMENDATION_MODEL": recommendationModel,
            "AI_GATEWAY_DEFAULT_MODEL": defaultModel,
        ]
        let stringFields: [(String, String)] = [
            ("AI_GATEWAY_CONSOLE_URL", "console_url"),
            ("AI_GATEWAY_DEPLOYMENT_LABEL", "deployment_label"),
            ("AI_GATEWAY_NETWORK_LABEL", "network_label"),
            ("AI_GATEWAY_REASONING_EFFORT", "reasoning_effort"),
        ]
        for (environmentKey, jsonKey) in stringFields {
            if let value = obj[jsonKey] as? String, !value.isEmpty {
                gateway[environmentKey] = value
            }
        }
        if let enabled = obj["thinking_enabled"] as? Bool {
            gateway["AI_GATEWAY_THINKING_ENABLED"] = enabled ? "true" : "false"
        }
        if let budget = obj["thinking_budget_tokens"] as? NSNumber {
            gateway["AI_GATEWAY_THINKING_BUDGET_TOKENS"] = budget.stringValue
        }
        if let inheritanceEnabled = obj["managed_app_inheritance_enabled"] as? Bool {
            gateway["MANAGED_AI_RUNTIME_ENABLED"] = inheritanceEnabled ? "true" : "false"
        }
        routeSangforGatewayThroughLocalRelay(&gateway, configuredBaseURL: baseURL)
        return gateway
    }

    /// Some enterprise VPN/aTrust deployments resolve their AI hostname only
    /// from macOS.  A locally running, loopback-only compatible relay can
    /// preserve that host route for Docker Desktop; this is intentionally an
    /// ephemeral compose override, never a persisted gateway preference or
    /// credential.  It is used only after an explicit Sangfor-compatible
    /// gateway was configured through the normal settings flow.
    private func routeSangforGatewayThroughLocalRelay(
        _ gateway: inout [String: String],
        configuredBaseURL: String
    ) {
        guard let host = URL(string: configuredBaseURL)?.host?.lowercased(),
              host == "aigateway.sangfor.com",
              httpOK("http://127.0.0.1:4319/api/health", timeout: 1) else {
            return
        }
        gateway["AI_GATEWAY_BASE_URL"] = "http://host.docker.internal:4319"
        log("检测到本机 AI 兼容转发器；Docker 将经受限宿主转发访问已配置网关")
    }

    /// A previously adopted stack may have been started before the launcher
    /// could read the Keychain.  Refresh only its stateless consumers when
    /// the authenticated status endpoint proves that configuration is absent,
    /// or when this launch selected the local relay but the old route is
    /// still unhealthy.
    private func gatewayServicesNeedRefresh(_ gateway: [String: String]?) -> Bool {
        guard let gateway, let token = composeEnv["API_TOKEN"], !token.isEmpty else {
            return false
        }
        // Run this short authenticated probe as a child process rather than
        // waiting on a URLSession callback while the native app is still
        // finishing launch.  The command and its output are never logged.
        let probe = runSync(
            "/usr/bin/curl",
            ["--fail", "--silent", "--show-error", "--max-time", "4",
             "-H", "Authorization: Bearer \(token)",
             "http://localhost:8000/api/ai-gateway/status"],
            timeout: 6
        )
        guard probe.status == 0,
              let data = probe.output.data(using: .utf8),
              let result = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return false
        }
        if result["configured"] as? Bool != true { return true }
        let selectedLocalRelay = gateway["AI_GATEWAY_BASE_URL"] == "http://host.docker.internal:4319"
        return selectedLocalRelay && result["healthy"] as? Bool != true
    }

    /// Compose failures occasionally include expanded connection strings. The
    /// native failure pane and launcher log therefore receive a redacted tail.
    private func redactedComposeOutput(_ output: String) -> String {
        var redacted = output
        for (key, value) in composeEnv where !value.isEmpty {
            let upper = key.uppercased()
            if upper.contains("KEY") || upper.contains("TOKEN") || upper.contains("PASSWORD") || upper.contains("SECRET") {
                redacted = redacted.replacingOccurrences(of: value, with: "[REDACTED]")
            }
        }
        return redacted
    }

    // MARK: Probing helpers

    private func portBound(_ port: Int) -> Bool {
        runSync("/usr/sbin/lsof", ["-nP", "-iTCP:\(port)", "-sTCP:LISTEN"], timeout: 5).status == 0
    }

    /// lax=false：仅 2xx/3xx 视为健康；lax=true：任何 HTTP 应答都视为存活
    /// （用于 web 根路径——dev server 可能返回应用级错误页，但进程是活的）。
    private func httpOK(_ urlString: String, timeout: TimeInterval = 3, lax: Bool = false) -> Bool {
        guard let url = URL(string: urlString) else { return false }
        var request = URLRequest(url: url)
        request.timeoutInterval = timeout
        let semaphore = DispatchSemaphore(value: 0)
        var ok = false
        let task = URLSession.shared.dataTask(with: request) { _, response, error in
            if let http = response as? HTTPURLResponse {
                if lax || (200..<400).contains(http.statusCode) {
                    ok = true
                } else {
                    log("健康探测 \(urlString) 返回 HTTP \(http.statusCode)")
                }
            } else if let error = error {
                log("健康探测 \(urlString) 失败：\(error.localizedDescription)")
            }
            semaphore.signal()
        }
        task.resume()
        if semaphore.wait(timeout: .now() + timeout + 2) == .timedOut {
            task.cancel()
        }
        return ok
    }

    private func randomHex(_ byteCount: Int) -> String {
        (0..<byteCount).map { _ in String(format: "%02x", UInt8.random(in: 0...255)) }.joined()
    }

    // MARK: Delegate plumbing

    private func status(_ text: String) {
        log(text)
        delegate?.launcherStatus(text)
    }

    private func fail(step: String, message: String, remedy: String) {
        state = .failed(step: step, message: message, remedy: remedy)
        log("启动失败 [\(step)] \(message) ｜ 建议：\(remedy)")
        delegate?.launcherFailed(step: step, message: message, remedy: remedy)
    }
}
