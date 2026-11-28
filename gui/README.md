# Tkinter GUI

The desktop control panel is a lightweight Tkinter application. It reads the available modules from `src/` and their display names and point values from each `properties.json`.

## Launch

From the repository root, inside the supported Debian/Ubuntu-based Linux VM:

```bash
sudo apt install python3-tk
python3 gui/main.py
```

The GUI uses Python's standard-library Tkinter module. On Debian/Ubuntu-based systems, the GUI binding is packaged separately as `python3-tk`; install it if it is not already present. The CLI launcher also checks and installs this package when it runs.

## Features

- Select or deselect vulnerability modules and save the selection to root `config.json`.
- Search the available modules, select all, or clear the selection.
- Run the existing `--setup`, `--start`, `--stop`, and `--report` commands through `main.sh`.
- Launch `--fix` in a terminal emulator so the CLI's existing confirmation prompts remain interactive.
- Display setup progress, recent log output from `cp-sim.log`, and live score data from `http://127.0.0.1:5000/api/scores`.

The selected module list is saved before running setup, start, fix, or report. The stop action does not rewrite configuration.

## Notes

- The GUI does not bypass the simulator's VM check or change the behavior of the command-line scripts.
- Live scores are available only while the Flask scoring service is running. Use **Start scoring** first.
- The **Fix selected** action requires a supported terminal emulator (for example, `x-terminal-emulator`, GNOME Terminal, Konsole, or Xfce Terminal). It retains the existing per-module confirmations.
- Setup progress reflects the module setup loop; it is not a percentage of total elapsed time.
- The log panel follows the root `cp-sim.log` file. Use the log file itself for the complete history.
