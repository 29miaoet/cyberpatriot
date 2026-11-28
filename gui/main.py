#!/usr/bin/env python3
"""Tkinter desktop interface for the CyberPatriot practice simulator."""
from __future__ import annotations

import json
import queue
import re
import shlex
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "src"
CONFIG_PATH = ROOT / "config.json"
LOG_PATH = ROOT / "cp-sim.log"
SCORES_URL = "http://127.0.0.1:5000/api/scores"
PROGRESS_RE = re.compile(r"Setup progress: (\d+)/(\d+)")
TTY_PROGRESS_RE = re.compile(r"Setup \[[#-]+\] (\d+)/(\d+)")
POLL_MS = 3000


def load_modules() -> tuple[list[dict[str, str]], list[str]]:
    """Return module metadata and the currently enabled module names."""
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        enabled = config.get("vulnerabilities", [])
        if not isinstance(enabled, list) or not all(isinstance(x, str) for x in enabled):
            raise ValueError("config.json must contain a vulnerabilities array.")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Could not load {CONFIG_PATH}: {exc}") from exc

    modules: list[dict[str, str]] = []
    for directory in sorted(SOURCE_DIR.iterdir()):
        if not directory.is_dir() or not (directory / "detect.sh").is_file():
            continue
        name = directory.name
        display = name.replace("_", " ").replace("-", " ").title()
        properties = directory / "properties.json"
        if properties.is_file():
            try:
                data = json.loads(properties.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("name"), str):
                    display = data["name"]
            except (OSError, json.JSONDecodeError):
                pass
        modules.append({"id": name, "name": display})
    known = {item["id"] for item in modules}
    unknown = [name for name in enabled if name not in known]
    if unknown:
        raise RuntimeError("config.json references missing modules: " + ", ".join(unknown))
    return modules, enabled


class CyberPatriotGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CyberPatriot Practice Simulator")
        self.root.geometry("1180x780")
        self.root.minsize(900, 620)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.running = False
        self.last_log_size = 0
        self.score_poll_enabled = True
        self.module_vars: dict[str, tk.BooleanVar] = {}
        self.module_rows: list[tuple[str, str, ttk.Frame]] = []
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.score_var = tk.StringVar(value="Waiting for scoring server")
        self.score_detail_var = tk.StringVar(value="Start the server to display live detector results.")
        self.progress_var = tk.DoubleVar(value=0)

        try:
            self.modules, enabled = load_modules()
        except RuntimeError as exc:
            messagebox.showerror("Configuration error", str(exc))
            raise

        self.enabled = set(enabled)
        self._build_ui()
        self._load_log_tail()
        self.root.after(150, self._process_events)
        self.root.after(1000, self._refresh_log)
        self.root.after(POLL_MS, self._poll_scores)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Header.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("Section.TLabel", font=("TkDefaultFont", 11, "bold"))
        style.configure("Action.TButton", padding=(10, 7))

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        ttk.Label(outer, text="CyberPatriot Practice Simulator", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Select the checks for this practice session, then run setup, scoring, remediation, or reporting.",
        ).pack(anchor="w", pady=(3, 12))

        content = ttk.Panedwindow(outer, orient=tk.HORIZONTAL)
        content.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(content, padding=(0, 0, 10, 0))
        right = ttk.Frame(content, padding=(10, 0, 0, 0))
        content.add(left, weight=3)
        content.add(right, weight=4)

        self._build_module_picker(left)
        self._build_actions(left)
        self._build_scores(right)
        self._build_logs(right)

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Label(footer, text="Logs: cp-sim.log").pack(side=tk.RIGHT)

    def _build_module_picker(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Vulnerability modules", style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text=f"{len(self.modules)} available").pack(side=tk.RIGHT)

        search = ttk.Entry(parent, textvariable=self.search_var)
        search.pack(fill=tk.X, pady=(8, 6))
        search.insert(0, "")
        self.search_var.trace_add("write", lambda *_: self._filter_modules())

        controls = ttk.Frame(parent)
        controls.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(controls, text="Select all", command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(controls, text="Select none", command=self._select_none).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Save selection", command=self._save_config).pack(side=tk.RIGHT)

        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        self.module_canvas = tk.Canvas(frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.module_canvas.yview)
        self.module_list = ttk.Frame(self.module_canvas)
        self.module_list.bind(
            "<Configure>",
            lambda _event: self.module_canvas.configure(scrollregion=self.module_canvas.bbox("all")),
        )
        self.module_window = self.module_canvas.create_window((0, 0), window=self.module_list, anchor="nw")
        self.module_canvas.configure(yscrollcommand=scrollbar.set)
        self.module_canvas.bind(
            "<Configure>",
            lambda event: self.module_canvas.itemconfigure(self.module_window, width=event.width),
        )
        self.module_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.module_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        for module in self.modules:
            name = module["id"]
            var = tk.BooleanVar(value=name in self.enabled)
            self.module_vars[name] = var
            row = ttk.Frame(self.module_list)
            row.pack(fill=tk.X, anchor="w")
            check = ttk.Checkbutton(row, text=module["name"], variable=var)
            check.pack(anchor="w", padx=4, pady=2)
            self.module_rows.append((name, module["name"].casefold(), row))

        ttk.Label(
            parent,
            text="The selection is saved to config.json and used by all command buttons.",
            wraplength=360,
        ).pack(anchor="w", pady=(6, 0))

    def _build_actions(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent).pack(fill=tk.X, pady=10)
        ttk.Label(parent, text="Commands", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        actions = ttk.Frame(parent)
        actions.pack(fill=tk.X)
        buttons = [
            ("Setup", "--setup", "Prepare the selected practice modules."),
            ("Start scoring", "--start", "Start the local Flask scoring server."),
            ("Stop scoring", "--stop", "Stop the background scoring server."),
            ("Fix selected", "--fix", "Open a terminal for the existing confirmation-based fixes."),
            ("Generate report", "--report", "Generate and open the Markdown scoring report."),
        ]
        self.action_buttons: list[ttk.Button] = []
        for label, flag, help_text in buttons:
            button = ttk.Button(
                actions,
                text=label,
                style="Action.TButton",
                command=lambda value=flag: self._run_action(value),
            )
            button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), pady=2)
            self.action_buttons.append(button)
            button.configure(cursor="hand2")
            button.bind("<Enter>", lambda _e, text=help_text: self.status_var.set(text))
            button.bind("<Leave>", lambda _e: self.status_var.set("Ready"))

        ttk.Label(parent, text="Setup progress", style="Section.TLabel").pack(anchor="w", pady=(10, 4))
        self.progress = ttk.Progressbar(parent, maximum=100, variable=self.progress_var, mode="determinate")
        self.progress.pack(fill=tk.X)
        self.progress_label = ttk.Label(parent, text="Idle")
        self.progress_label.pack(anchor="w", pady=(3, 0))

    def _build_scores(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Live score", style="Section.TLabel").pack(anchor="w")
        score_card = ttk.Frame(parent, padding=10, relief=tk.GROOVE)
        score_card.pack(fill=tk.X, pady=(6, 12))
        ttk.Label(score_card, textvariable=self.score_var, font=("TkDefaultFont", 20, "bold")).pack(anchor="w")
        ttk.Label(score_card, textvariable=self.score_detail_var, wraplength=500).pack(anchor="w", pady=(4, 0))

        ttk.Label(parent, text="Detector results", style="Section.TLabel").pack(anchor="w")
        columns = ("module", "status", "points", "detail")
        self.score_tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        for key, title, width in (
            ("module", "Check", 170), ("status", "Status", 90),
            ("points", "Points", 65), ("detail", "Details", 260),
        ):
            self.score_tree.heading(key, text=title)
            self.score_tree.column(key, width=width, anchor=tk.W)
        score_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.score_tree.yview)
        self.score_tree.configure(yscrollcommand=score_scroll.set)
        self.score_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        score_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_logs(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent).pack(fill=tk.X, pady=10)
        header = ttk.Frame(parent)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Application log", style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="Clear view", command=self._clear_log_view).pack(side=tk.RIGHT)
        log_frame = ttk.Frame(parent)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.log_text = tk.Text(
            log_frame, height=12, wrap=tk.WORD, state=tk.DISABLED,
            font=("TkFixedFont", 9), background="#171a21", foreground="#d8dee9",
            insertbackground="#ffffff",
        )
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.module_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _filter_modules(self) -> None:
        query = self.search_var.get().casefold().strip()
        for _name, label, row in self.module_rows:
            if query in label or query in _name:
                row.pack(fill=tk.X, anchor="w")
            else:
                row.pack_forget()

    def _select_all(self) -> None:
        for variable in self.module_vars.values():
            variable.set(True)

    def _select_none(self) -> None:
        for variable in self.module_vars.values():
            variable.set(False)

    def _save_config(self, *, quiet: bool = False) -> bool:
        selected = [name for name, variable in self.module_vars.items() if variable.get()]
        if not selected:
            if not quiet:
                messagebox.showwarning("No modules selected", "Select at least one vulnerability module.")
            return False
        try:
            current = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if not isinstance(current, dict):
                raise ValueError("config.json must contain a JSON object.")
            current["vulnerabilities"] = selected
            temporary = CONFIG_PATH.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
            temporary.replace(CONFIG_PATH)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("Could not save selection", str(exc))
            return False
        self.enabled = set(selected)
        self.status_var.set(f"Saved {len(selected)} selected modules.")
        if not quiet:
            self._append_log(f"Saved {len(selected)} modules to config.json.")
        return True

    def _run_action(self, flag: str) -> None:
        if self.running:
            return
        if flag != "--stop" and not self._save_config(quiet=True):
            return
        if flag == "--fix":
            self._launch_fix_terminal()
            return
        if flag == "--setup":
            self.progress_var.set(0)
            self.progress_label.configure(text="Preparing modules…")
        if flag == "--start":
            self.score_poll_enabled = True
        self.running = True
        self._set_buttons(False)
        self.status_var.set(f"Running {flag}…")
        self._append_log(f"$ ./main.sh {flag}")
        threading.Thread(target=self._run_cli, args=(flag,), daemon=True).start()

    def _run_cli(self, flag: str) -> None:
        try:
            process = subprocess.Popen(
                [str(ROOT / "main.sh"), flag],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.events.put(("output", line.rstrip()))
                match = PROGRESS_RE.search(line) or TTY_PROGRESS_RE.search(line)
                if match:
                    done, total = map(int, match.groups())
                    self.events.put(("progress", (done, total)))
            return_code = process.wait()
            self.events.put(("finished", (flag, return_code)))
        except OSError as exc:
            self.events.put(("output", f"Could not launch main.sh: {exc}"))
            self.events.put(("finished", (flag, 1)))

    def _launch_fix_terminal(self) -> None:
        if not messagebox.askyesno(
            "Run vulnerability remediation?",
            "The existing --fix scripts can modify system configuration and remove configured items. "
            "They retain their per-module confirmation prompts. Continue?",
        ):
            return
        terminals = ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal"]
        terminal = next((name for name in terminals if self._command_exists(name)), None)
        if terminal is None:
            messagebox.showerror(
                "Terminal not found",
                "No supported terminal emulator was found. Run ./main.sh --fix from a terminal instead.",
            )
            return
        command = f"cd {shlex.quote(str(ROOT))} && ./main.sh --fix; status=$?; echo; echo 'Command exited with status' $status; read -r -p 'Press Enter to close…'"
        try:
            if terminal == "gnome-terminal":
                subprocess.Popen([terminal, "--", "bash", "-lc", command], cwd=ROOT)
            elif terminal == "konsole":
                subprocess.Popen([terminal, "-e", "bash", "-lc", command], cwd=ROOT)
            elif terminal == "xfce4-terminal":
                subprocess.Popen([terminal, "--command", f"bash -lc {shlex.quote(command)}"], cwd=ROOT)
            else:
                subprocess.Popen([terminal, "-e", "bash", "-lc", command], cwd=ROOT)
            self.status_var.set("Remediation running in terminal; monitor cp-sim.log.")
            self._append_log("$ ./main.sh --fix (interactive terminal)")
        except OSError as exc:
            messagebox.showerror("Could not open terminal", str(exc))

    @staticmethod
    def _command_exists(name: str) -> bool:
        from shutil import which
        return which(name) is not None

    def _process_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "output":
                    self._append_log(str(payload))
                elif kind == "scores":
                    self._render_scores(payload)
                elif kind == "scores_unavailable":
                    if not self.running:
                        self.score_var.set("Scoring server unavailable")
                        self.score_detail_var.set("Use Start scoring to launch the local Flask service.")
                elif kind == "progress":
                    done, total = payload  # type: ignore[misc]
                    percentage = 100 * done / max(total, 1)
                    self.progress_var.set(percentage)
                    self.progress_label.configure(text=f"{done} of {total} modules ({percentage:.0f}%)")
                elif kind == "finished":
                    flag, code = payload  # type: ignore[misc]
                    self.running = False
                    self._set_buttons(True)
                    self.status_var.set(f"{flag} finished with exit code {code}.")
                    self._append_log(f"Process finished with exit code {code}.")
                    if flag == "--setup":
                        self.progress_var.set(100 if code == 0 else self.progress_var.get())
                        self.progress_label.configure(text="Setup completed." if code == 0 else "Setup stopped; see log.")
                    if flag == "--start" and code == 0:
                        self.score_poll_enabled = True
                        self._poll_scores()
                    if code != 0:
                        messagebox.showerror("Command failed", f"{flag} exited with status {code}. See cp-sim.log.")
        except queue.Empty:
            pass
        self.root.after(150, self._process_events)

    def _set_buttons(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in self.action_buttons:
            button.configure(state=state)

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log_view(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _load_log_tail(self) -> None:
        try:
            if LOG_PATH.is_file():
                lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-250:]
                for line in lines:
                    self._append_log(line)
                self.last_log_size = LOG_PATH.stat().st_size
        except OSError:
            pass

    def _refresh_log(self) -> None:
        try:
            if LOG_PATH.is_file():
                size = LOG_PATH.stat().st_size
                if size < self.last_log_size:
                    self.last_log_size = 0
                if size > self.last_log_size:
                    with LOG_PATH.open("r", encoding="utf-8", errors="replace") as log_file:
                        log_file.seek(self.last_log_size)
                        new_text = log_file.read()
                    self.last_log_size = size
                    for line in new_text.splitlines():
                        self._append_log(line)
        except OSError:
            pass
        self.root.after(1000, self._refresh_log)

    def _poll_scores(self) -> None:
        if self.score_poll_enabled:
            threading.Thread(target=self._fetch_scores, daemon=True).start()
        self.root.after(POLL_MS, self._poll_scores)

    def _fetch_scores(self) -> None:
        try:
            request = urllib.request.Request(SCORES_URL, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=2) as response:
                data = json.loads(response.read().decode("utf-8"))
            checks = data.get("checks", [])
            self.events.put(("scores", checks))
        except (OSError, urllib.error.URLError, json.JSONDecodeError, AttributeError):
            self.events.put(("scores_unavailable", None))

    def _render_scores(self, checks: object) -> None:
        if not isinstance(checks, list):
            return
        for item in self.score_tree.get_children():
            self.score_tree.delete(item)
        earned = possible = fixed = 0
        for check in checks:
            if not isinstance(check, dict):
                continue
            name = str(check.get("name", "Unknown"))
            status = str(check.get("status", "error")).title()
            points = check.get("points", 0)
            try:
                points = float(points)
            except (TypeError, ValueError):
                points = 0
            possible += points
            if status.lower() == "fixed":
                earned += points
                fixed += 1
            detail = str(check.get("detail") or check.get("message") or "")
            self.score_tree.insert("", tk.END, values=(name, status, f"{points:g}", detail))
        self.score_var.set(f"{earned:g} / {possible:g} points")
        self.score_detail_var.set(
            f"{fixed} of {len(checks)} checks fixed · "
            f"{(100 * earned / possible):.1f}% score" if possible else f"{len(checks)} checks returned"
        )

    def _handle_score_event(self, kind: str, payload: object) -> None:
        if kind == "scores":
            self._render_scores(payload)
        elif kind == "scores_unavailable" and not self.running:
            self.score_var.set("Scoring server unavailable")
            self.score_detail_var.set("Use Start scoring to launch the local Flask service.")

    def _close(self) -> None:
        self.root.destroy()


def main() -> int:
    if not (ROOT / "main.sh").is_file():
        print("Could not locate main.sh beside the gui directory.", file=sys.stderr)
        return 1
    root = tk.Tk()
    try:
        CyberPatriotGUI(root)
    except RuntimeError:
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
