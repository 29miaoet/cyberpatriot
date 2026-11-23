# cp-sim

cp-sim is a Linux virtual-machine-only CyberPatriot practice and scoring simulator. It organizes vulnerability modules under `src/`, optionally applies each module's simulated vulnerable-state setup, and presents detector results through a local web-based scoring report.

> **Safety requirement:** Run cp-sim only inside a disposable Linux virtual machine. The VM check is heuristic, not a guarantee. Take a VM snapshot before using `--apply`. The installer checks for a VM before installing system packages, but virtualization detection is not proof that a machine is disposable.

## Project specifications

1. **Target environment:** Debian/Ubuntu-based Linux virtual machines, including Ubuntu, Debian, and Linux Mint. The VM check is heuristic and may not recognize every hypervisor configuration.
2. **Project structure:** Each vulnerability is represented by a subdirectory under `src/` (for example, `src/ufw/`).
3. **Configuration:** The root `config.json` is one JSON object with a single `vulnerabilities` array. Each array element is the name of a directory directly under `src/`.
4. **Setup scripts:** A module may contain `setup.sh`. Setup scripts never run implicitly; they execute only when the user explicitly supplies `--apply`.
5. **Detection scripts:** A module may contain `detect.sh`. It returns:
   - `0`: the check is fixed;
   - `1`: the check remains unresolved;
   - any other exit status: detector error.
6. **Module index:** At startup, populate `templates/ReadMe.html` with the detected distribution name and project title, then generate `~/Desktop/README.html`. An optional root-level `UserReadMe.html` is inserted as custom HTML.
7. **Scoring report:** `templates/ScoringReport.html` is populated at startup using detector results and module metadata, then written to the repository-root `Scoring Report.html`. Module point values come from `properties.json` (`points`, defaulting to 1). Unresolved checks are omitted from the fixed-issue list; detector errors affect the overall status. Penalties, remote links, and internet connectivity are not currently scored; the report displays zero penalties, no remote links, and an explicit “Not checked” connectivity status.
8. **Desktop shortcut:** At startup, generate `~/Desktop/Scoring Report.desktop`. Double-clicking it launches `main.sh --open`, starts the local scoring service, and opens the report in the default browser. The terminal window remains open while the service runs; close it to stop the service. Some desktop environments require choosing **Allow Launching** or **Trust and Launch** once for a newly generated `.desktop` file.
9. **Backend exposure:** Flask binds only to `127.0.0.1`; the report is intended for local access from the VM.
10. **Long-running operation:** The Flask process remains running while the scoring page is in use. System-service installation and automatic daemonization are not included.

## Repository layout

```text
.
├── main.py
├── main.sh
├── config.json
├── requirements.txt
├── README.md
├── templates/
│   ├── ReadMe.html
│   └── ScoringReport.html
└── src/
    └── <module>/
        ├── setup.sh          # optional; only run with --apply
        └── detect.sh         # optional; checked by the scoring API
```

Generated at runtime in the VM:

- `Scoring Report.html` in the repository root
- `~/Desktop/README.html` — configured module index
- `~/Desktop/Scoring Report.desktop` — report launcher

## Installation and launch

Run from the repository root inside a Debian/Ubuntu-based Linux VM:

```bash
chmod +x main.sh
./main.sh
```

The installer:

1. Checks that it is running inside a detected VM before making system changes.
2. Installs `python3`, `python3-venv`, and `python3-pip` with APT if they are missing.
3. Creates the project-local `.venv/` virtual environment.
4. Installs the Python packages listed in `requirements.txt`.
5. Starts cp-sim in read-only mode by default.

The script uses `sudo` when not run as root. Internet access and permission to install APT packages are required on the first run. Subsequent runs reuse the virtual environment and do not reinstall already-present system packages. Optional report values can be set with `CP_SIM_TEAM_ID`, `CP_SIM_TITLE`, `CP_SIM_REPORT_TITLE`, and `CP_SIM_LINUX_ROOT_POLICY` environment variables.

To explicitly apply configured setup scripts before starting the service:

```bash
./main.sh --apply
```

Do not use `--apply` on a host machine or a VM containing data you need to preserve. For the current UFW module, the setup script disables UFW.

## Using the scoring report

- The installer starts the service and prints its local URL: [http://127.0.0.1:5000/](http://127.0.0.1:5000/).
- Alternatively, double-click **Scoring Report** on the VM desktop. The shortcut starts the service and opens the report in the default browser.
- Keep the terminal window open while viewing the report. Closing it stops the Flask service.
- Do not open the generated `Scoring Report.html` directly as a local file. It must be served by Flask; each page load regenerates the report from current detector results, and the template refreshes the page every 60 seconds.
- The page refreshes detector results every five seconds.

## Configuration

Edit `config.json` to select module directories:

```json
{
  "vulnerabilities": [
    "ufw"
  ]
}
```

Names must refer to existing directories directly inside `src/`. Duplicate names and path traversal are rejected. A module's optional `properties.json` may define `name`, `points` (non-negative integer; default 1), `fix`, and `vulnerability` for report labels and hints.

## Module contract

A module is selected by its directory name in `config.json`. Both scripts are optional:

- `setup.sh` prepares the module's configured practice state. It may make system changes and therefore runs only under `--apply`.
- `detect.sh` checks the relevant condition. It must use exit code `0` only when the condition is fixed, and `1` when it is not fixed. Other statuses are treated as errors.

Scripts are invoked with Bash, with their module directory as the working directory. Each invocation has a 120-second timeout.

## Current implementation scope

The application provides configuration parsing, VM gating, opt-in setup execution, rendered HTML templates, a desktop launcher, and the Flask scoring API. It does not install system services, daemonize itself, or provide a general-purpose repair/fix workflow. Additional vulnerability modules and their detection logic are maintained separately under `src/`.
