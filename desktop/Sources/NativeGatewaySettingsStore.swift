import Foundation
import Security

enum NativeGatewaySettingsStore {
    static let keychainService = "BudgetLoop AI Gateway API Key"
    private static let replacementKeychainService = "BudgetLoop AI Gateway API Key v2"
    private static let allowedKinds = Set(["compatible", "new-api", "litellm"])
    private static let stringFields = [
        "kind", "base_url", "console_url", "recommendation_model", "default_model",
        "deployment_label", "network_label", "reasoning_effort",
    ]

    static func readSecret(service: String = keychainService) -> String? {
        let services = service == keychainService
            ? [replacementKeychainService, keychainService]
            : [service]
        for candidate in services {
            if let secret = readSecretWithSystemTool(candidate) {
                return secret
            }
        }
        return nil
    }

    private static func readSecretWithSystemTool(_ service: String) -> String? {
        // Security.framework + LAContext can block indefinitely under some
        // managed-device policies even when interaction is disabled. The
        // system Keychain CLI uses the same login Keychain and returns without
        // showing UI for our after-first-unlock item. Output stays process-only.
        let result = runSync(
            "/usr/bin/security",
            ["find-generic-password", "-a", NSUserName(), "-s", service, "-w"],
            timeout: 5
        )
        guard result.status == 0, !result.timedOut else {
            return nil
        }
        let secret = result.output.trimmingCharacters(in: .whitespacesAndNewlines)
        return secret.isEmpty ? nil : secret
    }

    static func save(settings: [String: Any], apiKey: String?) throws -> [String: Any] {
        let selected = try validate(settings)
        let submittedSecret = apiKey?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !submittedSecret.isEmpty {
            try writeSecret(submittedSecret)
        } else if readSecretWithSystemTool(replacementKeychainService) == nil,
                  let legacySecret = readLegacySecretForForegroundMigration() {
            // The old item may require one foreground Keychain approval. Move
            // it into the app-owned after-first-unlock slot while the operator
            // is explicitly saving settings; later launches stay silent.
            try writeSecret(legacySecret)
        }
        let directory = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/BudgetLoop", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true,
                                                attributes: [.posixPermissions: 0o700])
        let destination = directory.appendingPathComponent("ai-gateway.json")
        let data = try JSONSerialization.data(withJSONObject: selected, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: destination, options: [.atomic])
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: destination.path)
        return selected.merging([
            "secret_configured": readSecret() != nil,
            "secret_store": "macos_keychain",
        ]) { _, new in new }
    }

    private static func readLegacySecretForForegroundMigration() -> String? {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: NSUserName(),
            kSecAttrService: keychainService,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess,
              let data = result as? Data,
              let secret = String(data: data, encoding: .utf8),
              !secret.isEmpty else {
            return nil
        }
        return secret
    }

    private static func validate(_ settings: [String: Any]) throws -> [String: Any] {
        var selected: [String: Any] = [:]
        for field in stringFields {
            let value = (settings[field] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            guard value.count <= 120, !containsControlCharacter(value) else {
                throw NativeGatewaySettingsError.invalidSetting(field)
            }
            selected[field] = value
        }
        guard let kind = selected["kind"] as? String, allowedKinds.contains(kind) else {
            throw NativeGatewaySettingsError.invalidSetting("kind")
        }
        guard let rawURL = selected["base_url"] as? String,
              let url = URL(string: rawURL),
              ["https", "http"].contains(url.scheme?.lowercased() ?? ""),
              url.host != nil, url.user == nil, url.password == nil,
              url.query == nil, url.fragment == nil else {
            throw NativeGatewaySettingsError.invalidSetting("base_url")
        }
        let effort = selected["reasoning_effort"] as? String ?? ""
        guard ["", "low", "medium", "high", "max"].contains(effort.lowercased()) else {
            throw NativeGatewaySettingsError.invalidSetting("reasoning_effort")
        }
        let thinkingEnabled = settings["thinking_enabled"] as? Bool ?? false
        let thinkingBudget = settings["thinking_budget_tokens"] as? Int ?? 0
        guard (0...65_536).contains(thinkingBudget) else {
            throw NativeGatewaySettingsError.invalidSetting("thinking_budget_tokens")
        }
        selected["thinking_enabled"] = thinkingEnabled
        selected["thinking_budget_tokens"] = thinkingEnabled ? thinkingBudget : 0
        selected["managed_app_inheritance_enabled"] = settings["managed_app_inheritance_enabled"] as? Bool ?? true
        return selected
    }

    private static func writeSecret(_ secret: String) throws {
        guard secret.count <= 8_192, !containsControlCharacter(secret) else {
            throw NativeGatewaySettingsError.invalidSecret
        }
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: NSUserName(),
            // Never update a legacy item whose access policy may block the
            // foreground app. New saves use the app-owned v2 slot and take
            // precedence on later reads.
            kSecAttrService: replacementKeychainService,
        ]
        let attributes: [CFString: Any] = [kSecValueData: Data(secret.utf8)]
        let updateStatus = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if updateStatus == errSecSuccess { return }
        guard updateStatus == errSecItemNotFound else { throw NativeGatewaySettingsError.keychain(updateStatus) }
        var addition = query
        addition[kSecValueData] = Data(secret.utf8)
        addition[kSecAttrAccessible] = kSecAttrAccessibleAfterFirstUnlock
        let addStatus = SecItemAdd(addition as CFDictionary, nil)
        guard addStatus == errSecSuccess else { throw NativeGatewaySettingsError.keychain(addStatus) }
    }

    private static func containsControlCharacter(_ value: String) -> Bool {
        value.unicodeScalars.contains { scalar in
            scalar.properties.generalCategory == .control
        }
    }
}

enum NativeGatewaySettingsError: LocalizedError {
    case invalidSetting(String)
    case invalidSecret
    case keychain(OSStatus)

    var errorDescription: String? {
        switch self {
        case .invalidSetting(let field): return "设置字段无效：\(field)"
        case .invalidSecret: return "API Key 无效"
        case .keychain: return "macOS Keychain 未能保存该 API Key"
        }
    }
}
