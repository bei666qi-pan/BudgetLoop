import Cocoa
import WebKit

// MARK: - 启动进度 / 失败状态窗口

final class StatusWindowController: NSWindowController, NSWindowDelegate {
    /// 用户关闭窗口时回调（由 AppDelegate 决定退出与收尾）。
    var onClose: (() -> Void)?

    private let statusLabel = NSTextField(wrappingLabelWithString: "")
    private let eyebrowLabel = NSTextField(labelWithString: "本机工作台")
    private let titleLabel = NSTextField(labelWithString: "正在准备 BudgetLoop")
    private let detailLabel = NSTextField(wrappingLabelWithString: "Docker、工作区与受限 AI 能力将在本机完成初始化。")
    private let stageLabel = NSTextField(labelWithString: "正在检查运行环境")
    private let stageTrack = NSStackView()
    private let markImageView = NSImageView()
    private let activityGlow = NSView()
    private let progress = NSProgressIndicator()
    private let quitButton = NSButton(title: "退出", target: nil, action: nil)
    private let retryHint = NSTextField(wrappingLabelWithString: "准备期间可以安全地最小化此窗口。")
    private var stageDots: [NSView] = []
    private var hasFailed = false

    private let reducedMotion = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion

    init() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 560, height: 396),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered, defer: false)
        window.title = "BudgetLoop · 正在启动"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.isMovableByWindowBackground = true
        window.backgroundColor = .clear
        window.center()
        super.init(window: window)
        window.delegate = self

        guard let content = window.contentView else { return }
        content.wantsLayer = true

        let background = NSVisualEffectView(frame: content.bounds)
        background.material = .underWindowBackground
        background.blendingMode = .behindWindow
        background.state = .active
        background.autoresizingMask = [.width, .height]
        content.addSubview(background)

        let gradient = CAGradientLayer()
        gradient.colors = [
            NSColor(calibratedRed: 0.90, green: 0.97, blue: 1.0, alpha: 0.98).cgColor,
            NSColor(calibratedRed: 0.78, green: 0.91, blue: 0.99, alpha: 0.96).cgColor,
            NSColor(calibratedRed: 0.94, green: 0.98, blue: 1.0, alpha: 0.98).cgColor,
        ]
        gradient.locations = [0, 0.52, 1]
        gradient.startPoint = CGPoint(x: 0, y: 1)
        gradient.endPoint = CGPoint(x: 1, y: 0)
        gradient.frame = content.bounds
        content.layer?.insertSublayer(gradient, at: 0)

        let card = NSVisualEffectView(frame: NSRect(x: 24, y: 24, width: 512, height: 348))
        card.material = .popover
        card.blendingMode = .withinWindow
        card.state = .active
        card.wantsLayer = true
        card.layer?.cornerRadius = 28
        card.layer?.borderWidth = 1
        card.layer?.borderColor = NSColor.white.withAlphaComponent(0.72).cgColor
        card.layer?.shadowColor = NSColor(calibratedRed: 0.13, green: 0.40, blue: 0.62, alpha: 0.18).cgColor
        card.layer?.shadowOpacity = 1
        card.layer?.shadowRadius = 24
        card.layer?.shadowOffset = NSSize(width: 0, height: -4)
        content.addSubview(card)

        activityGlow.frame = NSRect(x: 51, y: 247, width: 92, height: 92)
        activityGlow.wantsLayer = true
        activityGlow.layer?.backgroundColor = NSColor(calibratedRed: 0.25, green: 0.68, blue: 0.96, alpha: 0.16).cgColor
        activityGlow.layer?.cornerRadius = 46
        card.addSubview(activityGlow)

        markImageView.frame = NSRect(x: 61, y: 257, width: 72, height: 72)
        markImageView.image = NSImage(named: "BudgetLoop")
            ?? Bundle.main.path(forResource: "BudgetLoop", ofType: "icns").flatMap(NSImage.init(contentsOfFile:))
        markImageView.imageScaling = .scaleProportionallyUpOrDown
        markImageView.setAccessibilityLabel("BudgetLoop 标志")
        card.addSubview(markImageView)

        eyebrowLabel.font = .systemFont(ofSize: 12, weight: .semibold)
        eyebrowLabel.textColor = NSColor(calibratedRed: 0.08, green: 0.36, blue: 0.61, alpha: 1)
        eyebrowLabel.frame = NSRect(x: 160, y: 307, width: 300, height: 20)
        card.addSubview(eyebrowLabel)

        titleLabel.font = .systemFont(ofSize: 25, weight: .bold)
        titleLabel.textColor = NSColor(calibratedWhite: 0.09, alpha: 1)
        titleLabel.frame = NSRect(x: 160, y: 269, width: 322, height: 34)
        card.addSubview(titleLabel)

        detailLabel.font = .systemFont(ofSize: 13, weight: .regular)
        detailLabel.textColor = NSColor(calibratedWhite: 0.28, alpha: 1)
        detailLabel.maximumNumberOfLines = 2
        detailLabel.frame = NSRect(x: 160, y: 225, width: 304, height: 38)
        card.addSubview(detailLabel)

        stageTrack.orientation = .horizontal
        stageTrack.spacing = 8
        stageTrack.distribution = .fillEqually
        stageTrack.alignment = .centerY
        stageTrack.frame = NSRect(x: 54, y: 183, width: 404, height: 8)
        for _ in 0..<5 {
            let dot = NSView(frame: NSRect(x: 0, y: 0, width: 75, height: 6))
            dot.wantsLayer = true
            dot.layer?.cornerRadius = 3
            stageTrack.addArrangedSubview(dot)
            stageDots.append(dot)
        }
        card.addSubview(stageTrack)

        stageLabel.font = .systemFont(ofSize: 13, weight: .semibold)
        stageLabel.textColor = NSColor(calibratedRed: 0.06, green: 0.28, blue: 0.49, alpha: 1)
        stageLabel.frame = NSRect(x: 54, y: 149, width: 404, height: 21)
        stageLabel.setAccessibilityLabel("启动阶段")
        card.addSubview(stageLabel)

        progress.style = .spinning
        progress.controlSize = .small
        progress.frame = NSRect(x: 54, y: 103, width: 20, height: 20)
        progress.startAnimation(nil)
        progress.setAccessibilityLabel("正在启动")
        card.addSubview(progress)

        statusLabel.font = NSFont.systemFont(ofSize: 13, weight: .regular)
        statusLabel.textColor = NSColor(calibratedWhite: 0.29, alpha: 1)
        statusLabel.maximumNumberOfLines = 2
        statusLabel.frame = NSRect(x: 84, y: 94, width: 374, height: 38)
        statusLabel.stringValue = "正在启动…"
        statusLabel.setAccessibilityLabel("当前启动状态")
        card.addSubview(statusLabel)

        retryHint.font = .systemFont(ofSize: 11, weight: .regular)
        retryHint.textColor = NSColor(calibratedWhite: 0.43, alpha: 1)
        retryHint.frame = NSRect(x: 54, y: 52, width: 348, height: 20)
        card.addSubview(retryHint)

        quitButton.bezelStyle = .rounded
        quitButton.controlSize = .regular
        quitButton.frame = NSRect(x: 416, y: 44, width: 52, height: 30)
        quitButton.target = self
        quitButton.action = #selector(quitClicked)
        quitButton.isHidden = true
        quitButton.setAccessibilityLabel("退出 BudgetLoop")
        card.addSubview(quitButton)

        updateStage(for: "正在启动…", animated: false)
        startAmbientMotionIfNeeded()
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    func showStatus(_ text: String) {
        guard !hasFailed else { return }
        statusLabel.stringValue = text
        updateStage(for: text, animated: !reducedMotion)
    }

    func showFailure(step: String, message: String, remedy: String) {
        hasFailed = true
        window?.title = "BudgetLoop 启动失败"
        progress.stopAnimation(nil)
        progress.isHidden = true
        activityGlow.layer?.removeAnimation(forKey: "budgetloop.breathe")
        eyebrowLabel.stringValue = "需要一点处理"
        titleLabel.stringValue = "启动暂未完成"
        detailLabel.stringValue = "服务没有按预期就绪。已保留本机配置与已运行的数据服务。"
        stageTrack.isHidden = true
        stageLabel.stringValue = "失败步骤：\(step)"
        stageLabel.textColor = NSColor.systemRed
        statusLabel.maximumNumberOfLines = 0
        statusLabel.frame = NSRect(x: 54, y: 91, width: 404, height: 90)
        statusLabel.stringValue = "\(message)\n\n解决办法：\(remedy)"
        retryHint.stringValue = "修复后重新打开 BudgetLoop 即可继续。"
        quitButton.isHidden = false
    }

    private func updateStage(for text: String, animated: Bool) {
        let index: Int
        let label: String
        switch text {
        case let value where value.contains("Docker"):
            index = 0; label = "正在确认本机运行环境"
        case let value where value.contains("环境配置") || value.contains(".env"):
            index = 1; label = "正在整理本机安全配置"
        case let value where value.contains("启动 BudgetLoop") || value.contains("启动服务"):
            index = 2; label = "正在唤醒本地服务"
        case let value where value.contains("健康检查") || value.contains("等待"):
            index = 3; label = "正在等待工作台就绪"
        default:
            index = 4; label = "正在连接工作台"
        }
        stageLabel.stringValue = label
        let updates = { [weak self] in
            guard let self else { return }
            for (offset, dot) in self.stageDots.enumerated() {
                let active = offset <= index
                dot.layer?.backgroundColor = (active
                    ? NSColor(calibratedRed: 0.11, green: 0.48, blue: 0.83, alpha: 1)
                    : NSColor(calibratedRed: 0.34, green: 0.63, blue: 0.82, alpha: 0.18)).cgColor
                dot.layer?.opacity = active ? 1 : 0.68
            }
            self.activityGlow.layer?.backgroundColor = NSColor(
                calibratedRed: 0.25, green: 0.68, blue: 0.96, alpha: 0.10 + (Double(index) * 0.025)
            ).cgColor
        }
        if animated {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.28
                context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
                updates()
            }
        } else {
            updates()
        }
    }

    private func startAmbientMotionIfNeeded() {
        guard !reducedMotion, let layer = activityGlow.layer else { return }
        let breathe = CABasicAnimation(keyPath: "opacity")
        breathe.fromValue = 0.56
        breathe.toValue = 1.0
        breathe.duration = 1.6
        breathe.autoreverses = true
        breathe.repeatCount = .infinity
        breathe.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
        layer.add(breathe, forKey: "budgetloop.breathe")
    }

    @objc private func quitClicked() {
        NSApp.terminate(nil)
    }

    func windowWillClose(_ notification: Notification) {
        onClose?()
    }
}

// MARK: - 主窗口（WKWebView + 文件夹选择桥接）

final class WebWindowController: NSWindowController, NSWindowDelegate, WKScriptMessageHandler {
    var onClose: (() -> Void)?
    var onGatewaySettingsSaved: ((@escaping (Bool, String?) -> Void) -> Void)?

    private let webView = WKWebView()
    init(url: URL) {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1280, height: 840),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        window.title = "BudgetLoop"
        window.center()
        super.init(window: window)
        window.delegate = self
        webView.configuration.userContentController.add(self, name: "budgetloopPickProjectDir")
        webView.configuration.userContentController.add(self, name: "budgetloopSaveGatewaySettings")

        if let content = window.contentView {
            webView.frame = content.bounds
            webView.autoresizingMask = [.width, .height]
            content.addSubview(webView)
        }

        webView.load(URLRequest(url: url))
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    deinit {
        webView.configuration.userContentController.removeScriptMessageHandler(
            forName: "budgetloopPickProjectDir")
        webView.configuration.userContentController.removeScriptMessageHandler(
            forName: "budgetloopSaveGatewaySettings")
    }

    func windowWillClose(_ notification: Notification) {
        onClose?()
    }

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        switch message.name {
        case "budgetloopPickProjectDir":
            pickFolder()
        case "budgetloopSaveGatewaySettings":
            saveGatewaySettings(from: message)
        default:
            return
        }
    }

    // MARK: 文件夹选择 → 注入网页表单

    @objc private func pickFolder() {
        guard let window = window else { return }
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = true
        panel.prompt = "选择文件夹"
        panel.message = "选择要授权给 BudgetLoop 任务的项目文件夹"
        panel.beginSheetModal(for: window) { [weak self] response in
            guard let self = self, response == .OK, let url = panel.url else { return }
            guard let data = try? JSONEncoder().encode(url.path),
                  let jsonPath = String(data: data, encoding: .utf8) else { return }
            let script = "window.budgetloopSetProjectDir && window.budgetloopSetProjectDir(\(jsonPath))"
            self.webView.evaluateJavaScript(script, completionHandler: nil)
        }
    }

    // MARK: 网页 AI 设置 → 本机安全存储

    /// Only the app's main localhost page can invoke this bridge. The result
    /// intentionally contains redacted configuration and never the API key.
    private func saveGatewaySettings(from message: WKScriptMessage) {
        guard isTrustedLocalPage(message),
              let body = message.body as? [String: Any],
              let requestID = body["id"] as? String,
              requestID.count <= 128,
              let settings = body["settings"] as? [String: Any] else {
            return
        }
        let apiKey = body["api_key"] as? String
        do {
            let saved = try NativeGatewaySettingsStore.save(settings: settings, apiKey: apiKey)
            guard let applySettings = onGatewaySettingsSaved else {
                dispatchGatewaySaveResult(id: requestID, ok: true, settings: saved, message: nil)
                return
            }
            applySettings { [weak self] applied, errorMessage in
                DispatchQueue.main.async {
                    if applied {
                        self?.dispatchGatewaySaveResult(id: requestID, ok: true, settings: saved, message: nil)
                    } else {
                        self?.dispatchGatewaySaveResult(id: requestID, ok: false, settings: nil,
                                                        message: errorMessage ?? "本机服务未能应用设置")
                    }
                }
            }
        } catch {
            dispatchGatewaySaveResult(id: requestID, ok: false, settings: nil,
                                      message: error.localizedDescription)
        }
    }

    private func isTrustedLocalPage(_ message: WKScriptMessage) -> Bool {
        guard message.frameInfo.isMainFrame,
              let url = message.frameInfo.request.url else { return false }
        return url.scheme == "http" && url.host?.lowercased() == "localhost" && url.port == 3000
    }

    private func dispatchGatewaySaveResult(id: String, ok: Bool,
                                           settings: [String: Any]?, message: String?) {
        var result: [String: Any] = ["id": id, "ok": ok]
        if let settings { result["settings"] = settings }
        if let message { result["message"] = message }
        guard JSONSerialization.isValidJSONObject(result),
              let data = try? JSONSerialization.data(withJSONObject: result, options: []),
              let json = String(data: data, encoding: .utf8) else { return }
        let script = "window.dispatchEvent(new CustomEvent('budgetloopGatewaySettingsSaved', { detail: \(json) }))"
        webView.evaluateJavaScript(script, completionHandler: nil)
    }
}
