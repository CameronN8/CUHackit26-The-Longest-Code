#!/usr/bin/env python3
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk

ROOT_DIR = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT_DIR / "main.py"


class CatanGuiController:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Catan Big Screen Controller")
        self.root.configure(bg="#111111")
        self.root.attributes("-fullscreen", True)

        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()

        self._build_ui()
        self._poll_log_queue()

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#111111")
        style.configure("TLabel", background="#111111", foreground="#f5f5f5", font=("Helvetica", 14))
        style.configure("Header.TLabel", font=("Helvetica", 22, "bold"))
        style.configure("TCheckbutton", background="#111111", foreground="#f5f5f5", font=("Helvetica", 13))
        style.configure("TButton", font=("Helvetica", 13, "bold"), padding=8)
        style.configure("TEntry", font=("Helvetica", 13))

        container = ttk.Frame(self.root, padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Catan Runtime Control", style="Header.TLabel").pack(anchor="w")

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(18, 12))

        ttk.Label(controls, text="Camera Index:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        self.camera_var = tk.StringVar(value="1")
        ttk.Entry(controls, textvariable=self.camera_var, width=8).grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(controls, text="Max Turns:").grid(row=0, column=2, sticky="w", padx=(18, 8), pady=6)
        self.max_turns_var = tk.StringVar(value="200")
        ttk.Entry(controls, textvariable=self.max_turns_var, width=8).grid(row=0, column=3, sticky="w", pady=6)

        ttk.Label(controls, text="Seed (optional):").grid(row=0, column=4, sticky="w", padx=(18, 8), pady=6)
        self.seed_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self.seed_var, width=12).grid(row=0, column=5, sticky="w", pady=6)

        self.interactive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Interactive", variable=self.interactive_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=6)

        self.detect_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Enable Detection", variable=self.detect_var).grid(row=1, column=2, columnspan=2, sticky="w", pady=6)

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(0, 12))

        self.start_button = ttk.Button(button_row, text="Start Game", command=self.start_game)
        self.start_button.pack(side="left", padx=(0, 10))

        self.stop_button = ttk.Button(button_row, text="Stop Game", command=self.stop_game, state="disabled")
        self.stop_button.pack(side="left", padx=(0, 10))

        ttk.Button(button_row, text="Exit", command=self.exit_app).pack(side="right")

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(container, textvariable=self.status_var).pack(anchor="w", pady=(0, 8))

        self.log_text = tk.Text(
            container,
            bg="#1b1b1b",
            fg="#e7e7e7",
            insertbackground="#e7e7e7",
            wrap="word",
            font=("Consolas", 12),
            relief="flat",
            padx=12,
            pady=10,
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        self.root.bind("<Escape>", lambda _e: self.toggle_fullscreen(False))
        self.root.bind("<F11>", lambda _e: self.toggle_fullscreen(True))

    def toggle_fullscreen(self, on: bool) -> None:
        self.root.attributes("-fullscreen", on)

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_log_queue(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)
        self.root.after(100, self._poll_log_queue)

    def _set_running_ui(self, running: bool) -> None:
        if running:
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.status_var.set("Running")
        else:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status_var.set("Idle")

    def _build_command(self) -> list[str]:
        cmd = [sys.executable, str(MAIN_PY)]

        camera = self.camera_var.get().strip()
        max_turns = self.max_turns_var.get().strip()
        seed = self.seed_var.get().strip()

        if camera:
            cmd += ["--camera-index", camera]
        if max_turns:
            cmd += ["--max-turns", max_turns]
        if seed:
            cmd += ["--seed", seed]
        if self.interactive_var.get():
            cmd.append("--interactive")

        if not self.detect_var.get():
            # Disable detection by forcing an invalid profile path that triggers fallback no-op.
            cmd += ["--hsv-profile", str(ROOT_DIR / "big_screen_testing" / "_disable_detection.json")]

        return cmd

    def start_game(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.log_queue.put("[GUI] Game is already running.\n")
            return

        if not MAIN_PY.exists():
            self.log_queue.put(f"[GUI] ERROR: Cannot find {MAIN_PY}\n")
            return

        cmd = self._build_command()
        self.log_queue.put(f"[GUI] Starting: {' '.join(cmd)}\n")

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            self.log_queue.put(f"[GUI] Failed to start process: {exc}\n")
            self.process = None
            return

        self._set_running_ui(True)
        threading.Thread(target=self._reader_thread, daemon=True).start()
        self.root.after(300, self._monitor_process)

    def _reader_thread(self) -> None:
        if self.process is None or self.process.stdout is None:
            return

        try:
            for line in self.process.stdout:
                self.log_queue.put(line)
        finally:
            try:
                self.process.stdout.close()
            except Exception:
                pass

    def _monitor_process(self) -> None:
        if self.process is None:
            self._set_running_ui(False)
            return

        code = self.process.poll()
        if code is None:
            self.root.after(300, self._monitor_process)
            return

        self.log_queue.put(f"[GUI] Process exited with code {code}\n")
        self.process = None
        self._set_running_ui(False)

    def stop_game(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self._set_running_ui(False)
            return

        self.log_queue.put("[GUI] Stopping game process...\n")
        self.process.terminate()

    def exit_app(self) -> None:
        self.stop_game()
        self.root.after(250, self.root.destroy)


def main() -> None:
    root = tk.Tk()
    app = CatanGuiController(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()


if __name__ == "__main__":
    main()
