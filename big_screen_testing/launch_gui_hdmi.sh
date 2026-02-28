#!/usr/bin/env bash
set -euo pipefail

# Launches this project's GUI app onto the Raspberry Pi's local HDMI desktop
# even when triggered from a headless SSH shell.

GUI_USER="${GUI_USER:-$(id -un)}"
GUI_UID="$(id -u "$GUI_USER")"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
APP_ENTRY="${APP_ENTRY:-$SCRIPT_DIR/gui_controller.py}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_ARGS="${APP_ARGS:-}"

if [ ! -f "$APP_ENTRY" ]; then
  echo "ERROR: APP_ENTRY not found: $APP_ENTRY" >&2
  exit 1
fi

RUN_CMD="cd \"$SCRIPT_DIR\" && exec \"$PYTHON_BIN\" \"$APP_ENTRY\" $APP_ARGS"

run_as_gui_user() {
  local env_prefix="$1"
  if [ "$(id -un)" = "$GUI_USER" ]; then
    eval "$env_prefix bash -lc '$RUN_CMD'"
  else
    if ! command -v sudo >/dev/null 2>&1; then
      echo "ERROR: Not running as $GUI_USER and sudo is unavailable." >&2
      echo "Run via: ssh $GUI_USER@<pi-ip> '<script path>'" >&2
      exit 1
    fi
    sudo -u "$GUI_USER" bash -lc "$env_prefix bash -lc '$RUN_CMD'"
  fi
}

# Wayland (default on recent Raspberry Pi OS desktop)
if [ -S "/run/user/$GUI_UID/wayland-0" ]; then
  run_as_gui_user "export XDG_RUNTIME_DIR=/run/user/$GUI_UID WAYLAND_DISPLAY=wayland-0 DISPLAY=:0;"
  exit 0
fi

# X11 fallback
run_as_gui_user "export DISPLAY=:0 XAUTHORITY=/home/$GUI_USER/.Xauthority;"
