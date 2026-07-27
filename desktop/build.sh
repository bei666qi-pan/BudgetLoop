#!/usr/bin/env bash
# 用系统 swiftc 直接编译 BudgetLoop.app（无 Xcode 工程），并拷贝到仓库根部。
# 幂等：重复执行会先清理旧产物再重新构建。
set -euo pipefail

DESKTOP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
APP_DIR="$DESKTOP_DIR/build/BudgetLoop.app"
BIN_PATH="$APP_DIR/Contents/MacOS/BudgetLoop"
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$DESKTOP_DIR/Info.plist")"
CANONICAL_VERSION="$(tr -d '[:space:]' < "$REPO_ROOT/VERSION")"
if [[ "$VERSION" != "$CANONICAL_VERSION" ]]; then
  echo "Info.plist version $VERSION does not match VERSION $CANONICAL_VERSION" >&2
  exit 1
fi
RELEASE_ZIP="$DESKTOP_DIR/build/BudgetLoop-v${VERSION}-macos.zip"
LOCAL_SIGN_IDENTITY="BudgetLoop Local Signing"
if [[ -n "${BUDGETLOOP_CODESIGN_IDENTITY:-}" ]]; then
  SIGN_IDENTITY="$BUDGETLOOP_CODESIGN_IDENTITY"
elif security find-certificate -c "$LOCAL_SIGN_IDENTITY" >/dev/null 2>&1; then
  SIGN_IDENTITY="$LOCAL_SIGN_IDENTITY"
else
  SIGN_IDENTITY="-"
fi

echo "==> 清理旧构建产物"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

echo "==> 编译 Swift 源码（swiftc -O，当前架构）"
swiftc -O \
    -o "$BIN_PATH" \
    "$DESKTOP_DIR/Sources/main.swift" \
    "$DESKTOP_DIR/Sources/LauncherCore.swift" \
    "$DESKTOP_DIR/Sources/NativeGatewaySettingsStore.swift" \
    "$DESKTOP_DIR/Sources/Windows.swift"

echo "==> 写入 Info.plist"
cp "$DESKTOP_DIR/Info.plist" "$APP_DIR/Contents/Info.plist"

echo "==> 写入 BudgetLoop 应用图标"
cp "$DESKTOP_DIR/Resources/BudgetLoop.icns" "$APP_DIR/Contents/Resources/BudgetLoop.icns"

echo "==> 签名并校验应用包（${SIGN_IDENTITY}）"
codesign --force --deep --sign "$SIGN_IDENTITY" "$APP_DIR"
codesign --verify --deep --strict --verbose=2 "$APP_DIR"

echo "==> 拷贝到仓库根部 $REPO_ROOT/BudgetLoop.app"
rm -rf "$REPO_ROOT/BudgetLoop.app"
ditto "$APP_DIR" "$REPO_ROOT/BudgetLoop.app"

echo "==> 生成本地安装归档"
rm -f "$RELEASE_ZIP"
ditto -c -k --sequesterRsrc --keepParent "$REPO_ROOT/BudgetLoop.app" "$RELEASE_ZIP"

BUILT_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP_DIR/Contents/Info.plist")"
if [[ "$BUILT_VERSION" != "$VERSION" ]]; then
  echo "Built app version $BUILT_VERSION does not match release $VERSION" >&2
  exit 1
fi

echo "==> 构建完成：$APP_DIR"
echo "    已安装：$REPO_ROOT/BudgetLoop.app"
echo "    归档：$RELEASE_ZIP"
