#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_DEVICE_NAME="iPhone 17 Pro"
DEFAULT_BUNDLE_ID="com.cascademountainweather.cascadeWeatherApp"

DEVICE_NAME="${DEVICE_NAME:-$DEFAULT_DEVICE_NAME}"
BUNDLE_ID="${BUNDLE_ID:-$DEFAULT_BUNDLE_ID}"
UDID="${UDID:-}"
SKIP_BUILD="false"

usage() {
  cat <<EOF
Usage: scripts/run_ios_sim.sh [options]

Options:
  --udid <id>           Simulator UDID to use
  --device <name>       Simulator device name (default: ${DEFAULT_DEVICE_NAME})
  --bundle-id <id>      App bundle id (default: ${DEFAULT_BUNDLE_ID})
  --skip-build          Skip flutter build step
  --help                Show this help

Environment overrides:
  UDID, DEVICE_NAME, BUNDLE_ID

Examples:
  scripts/run_ios_sim.sh
  scripts/run_ios_sim.sh --device "iPhone Air"
  scripts/run_ios_sim.sh --udid E663ACAD-EEBB-40D8-A55D-6E9884327C32
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --udid)
      UDID="$2"
      shift 2
      ;;
    --device)
      DEVICE_NAME="$2"
      shift 2
      ;;
    --bundle-id)
      BUNDLE_ID="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v flutter >/dev/null 2>&1; then
  echo "flutter not found in PATH" >&2
  exit 1
fi

if ! command -v xcrun >/dev/null 2>&1; then
  echo "xcrun not found (Xcode CLT required)" >&2
  exit 1
fi

resolve_udid() {
  if [[ -n "$UDID" ]]; then
    echo "$UDID"
    return
  fi

  local booted
  booted="$(xcrun simctl list devices | awk -v name="$DEVICE_NAME" '$0 ~ name && $0 ~ /\(Booted\)/ {gsub(/[()]/, "", $NF); print $NF; exit}')"
  if [[ -n "$booted" ]]; then
    echo "$booted"
    return
  fi

  local available
  available="$(xcrun simctl list devices available | awk -v name="$DEVICE_NAME" '$0 ~ name {gsub(/[()]/, "", $(NF-1)); print $(NF-1); exit}')"
  if [[ -n "$available" ]]; then
    echo "$available"
    return
  fi

  echo ""
}

TARGET_UDID="$(resolve_udid)"
if [[ -z "$TARGET_UDID" ]]; then
  echo "Could not find simulator device named: $DEVICE_NAME" >&2
  echo "Available devices:" >&2
  xcrun simctl list devices available | sed 's/^/  /' >&2
  exit 1
fi

echo "Using simulator: $TARGET_UDID"

if [[ "$SKIP_BUILD" != "true" ]]; then
  echo "Building iOS simulator app..."
  (cd "$APP_DIR" && flutter --suppress-analytics build ios --simulator)
fi

APP_PATH="$APP_DIR/build/ios/iphonesimulator/Runner.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Build output not found: $APP_PATH" >&2
  exit 1
fi

echo "Booting simulator..."
xcrun simctl boot "$TARGET_UDID" >/dev/null 2>&1 || true
xcrun simctl bootstatus "$TARGET_UDID" -b
open -a Simulator >/dev/null 2>&1 || true

echo "Installing app..."
xcrun simctl install "$TARGET_UDID" "$APP_PATH"

echo "Launching app..."
LAUNCH_OUTPUT="$(xcrun simctl launch "$TARGET_UDID" "$BUNDLE_ID" 2>&1)" || {
  echo "$LAUNCH_OUTPUT" >&2
  exit 1
}

echo "$LAUNCH_OUTPUT"
echo "Done."
