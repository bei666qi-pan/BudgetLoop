import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate, LauncherDelegate {
    private var statusWindow: StatusWindowController?
    private var webWindow: WebWindowController?
    private var core: LauncherCore?
    private var teardownStarted = false
    private var teardownFinished = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        let statusWC = StatusWindowController()
        statusWC.onClose = { NSApp.terminate(nil) }
        statusWC.showWindow(nil)
        statusWindow = statusWC

        let core = LauncherCore()
        core.delegate = self
        self.core = core
        core.start()
    }

    // MARK: LauncherDelegate（均在后台线程回调，切回主线程更新 UI）

    func launcherStatus(_ text: String) {
        DispatchQueue.main.async {
            self.statusWindow?.showStatus(text)
        }
    }

    func launcherReady(adopted: Bool, gatewayConfigured: Bool) {
        DispatchQueue.main.async {
            self.statusWindow?.window?.orderOut(nil)
            let webWC = WebWindowController(url: URL(string: "http://localhost:3000")!)
            webWC.onClose = { NSApp.terminate(nil) }
            webWC.onGatewaySettingsSaved = { [weak self] completion in
                guard let core = self?.core else {
                    completion(false, "BudgetLoop 启动器尚未就绪，请稍后重试。")
                    return
                }
                core.applySavedGatewaySettings(completion: completion)
            }
            webWC.showWindow(nil)
            self.webWindow = webWC
            // 仅当应用自己拉起了服务栈、且无法自动引导网关时，才提示手动配置。
            if !adopted && !gatewayConfigured {
                self.showGatewayGuidedSetup()
            }
        }
    }

    func launcherFailed(step: String, message: String, remedy: String) {
        DispatchQueue.main.async {
            self.statusWindow?.showFailure(step: step, message: message, remedy: remedy)
        }
    }

    // MARK: 收尾：只停应用自己启动的服务，adopt 的一律保留

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let core = core, core.needsTeardown, !teardownFinished else {
            return .terminateNow
        }
        if !teardownStarted {
            teardownStarted = true
            statusWindow?.showStatus("正在停止 BudgetLoop 服务…")
            statusWindow?.showWindow(nil)
            core.teardown {
                DispatchQueue.main.async {
                    self.teardownFinished = true
                    NSApp.reply(toApplicationShouldTerminate: true)
                }
            }
        }
        return .terminateLater
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    // MARK: 网关引导配置

    private func showGatewayGuidedSetup() {
        let alert = NSAlert()
        alert.messageText = "需要配置 AI 网关"
        alert.informativeText = "未找到本地网关配置或 Keychain 凭据，服务栈将以未配置网关的状态运行。请打开 new-api 控制台创建渠道与访问令牌，任务才能调用模型。"
        alert.addButton(withTitle: "打开网关控制台")
        alert.addButton(withTitle: "稍后配置")
        alert.alertStyle = .informational
        if let window = webWindow?.window {
            alert.beginSheetModal(for: window) { response in
                if response == .alertFirstButtonReturn {
                    NSWorkspace.shared.open(URL(string: "http://localhost:3001")!)
                }
            }
        } else if alert.runModal() == .alertFirstButtonReturn {
            NSWorkspace.shared.open(URL(string: "http://localhost:3001")!)
        }
    }
}

// MARK: - 入口

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
if #available(macOS 14.0, *) {
    app.activate()
} else {
    app.activate(ignoringOtherApps: true)
}
app.run()
