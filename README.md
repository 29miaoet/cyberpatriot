# cp-sim

cp-sim is a Linux virtual-machine-only CyberPatriot practice and scoring simulator. It organizes vulnerability modules under `src/`, optionally applies each module's simulated vulnerable-state setup, and presents detector results through a local web-based scoring report.

> **Safety requirement:** Run cp-sim only inside a disposable Linux virtual machine. The VM check is heuristic, not a guarantee. Take a VM snapshot before using `--apply`. The installer checks for a VM before installing system packages, but virtualization detection is not proof that a machine is disposable.

## Project specifications

1. **Target environment:** Debian/Ubuntu-based Linux virtual machines, including Ubuntu, Debian, and Linux Mint.
2. **Single entry point:** `main.sh` is the only supported entry point. It checks the VM environment, installs missing system dependencies, creates the project virtual environment, installs Python requirements, and starts the application.
3. **Application structure:** Python application code is organized in the `cp_sim/` package by responsibility. `cp_sim/__main__.py` coordinates startup; it is not intended to be invoked directly.
4. **Project modules:** Each vulnerability is represented by a subdirectory under `src/` (for example, `src/ufw/`).
5. **Configuration:** The root `config.json` is one JSON object with a single `vulnerabilities` array. Each element is the name of a directory directly under `src/`.
6. **Setup scripts:** A module may contain `setup.sh`. Setup scripts never run implicitly; they execute only when the user explicitly supplies `--apply`. The users module creates configured authorized accounts and grants the `sudo` group only to authorized administrators. Newly created accounts have locked passwords.
7. **User policy enforcement:** The users setup script creates authorized accounts, grants the `sudo` group to authorized administrators, removes unauthorized users, and demotes unauthorized administrators. It verifies the resulting account state and reports each action. Newly created accounts have locked passwords; assign passwords separately before interactive login.
8. **Generated README account lists:** When the users module is enabled, the generated desktop README displays the parsed `authorizedUsers` and `authorizedAdministrators` arrays from `src/users/users.json`.
9. **Detection scripts:** A module may contain `detect.sh`. It returns `0` when the check is fixed, `1` when unresolved, and any other status for detector errors.
10. **Module index:** At startup, populate `templates/ReadMe.html` with detected distribution information and write `~/Desktop/README.html`. An optional root-level `UserReadMe.html` is inserted as custom HTML.
11. **Scoring report:** Populate `templates/ScoringReport.html` at startup and on each report request, then write the repository-root `Scoring Report.html`. Module point values come from `properties.json` (`points`, default 1). The users module scores each distinct unauthorized user/admin finding at 3 points, with unauthorized-user removal taking precedence.
12. **Desktop shortcut:** Generate `~/Desktop/Scoring Report.desktop`. It opens `http://127.0.0.1:5000/` in the default browser; it does not start or manage Flask.
13. **Backend exposure:** Flask binds only to `127.0.0.1`; the report is intended for local access from the VM.
14. **Long-running operation:** The Flask process remains running while the scoring page is in use. System-service installation and automatic daemonization are not included.

## Repository layout

```text
.
├── main.sh                  # sole entry point
├── cp_sim/
│   ├── __init__.py
│   ├── __main__.py          # startup orchestration
│   ├── config.py            # paths and configuration validation
│   ├── environment.py       # VM checks and OS metadata
│   ├── modules.py           # setup execution and module metadata
│   ├── scoring.py           # detector execution and scoring records
│   ├── reports.py           # HTML and desktop artifact generation
│   └── web.py               # Flask app and HTTP routes
├── config.json
├── requirements.txt
├── templates/
│   ├── ReadMe.html
│   └── ScoringReport.html
└── src/
    └── <module>/
        ├── setup.sh         # optional; only run with --apply
        └── detect.sh        # optional; checked by the scoring API
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

The launcher:

1. Checks that it is running inside a detected VM before making system changes.
2. Installs `python3`, `python3-venv`, and `python3-pip` with APT if they are missing.
3. Creates the project-local `.venv/` virtual environment.
4. Installs the packages listed in `requirements.txt`.
5. Starts cp-sim in read-only mode by default.

The script uses `sudo` when not run as root. Internet access and permission to install APT packages are required on the first run. Subsequent runs reuse the virtual environment. Optional report values can be set with `CP_SIM_TEAM_ID`, `CP_SIM_TITLE`, `CP_SIM_REPORT_TITLE`, and `CP_SIM_LINUX_ROOT_POLICY` environment variables.

To explicitly apply configured setup scripts before starting the service:

```bash
./main.sh --apply
```

Do not use `--apply` on a host machine or a VM containing data you need to preserve. For the current UFW module, the setup script disables UFW.

## Using the scoring report

- The service prints its local URL: [http://127.0.0.1:5000/](http://127.0.0.1:5000/).
- Alternatively, double-click **Scoring Report** on the VM desktop. The Flask service must already be running.
- Keep the terminal running while viewing the report; closing it stops the service.
- Do not open `Scoring Report.html` directly as a local file. Each page load regenerates the report from current detector results.
- The report page refreshes periodically.

## Configuration

Edit `config.json` to select module directories:

```json
{
  "vulnerabilities": [
    "ufw",
    "users"
  ]
}
```

Names must refer to existing directories directly inside `src/`. Duplicate names and path traversal are rejected. A module's optional `properties.json` may define `name`, `points` (non-negative integer; default 1), `fix`, and `vulnerability`.

The `src/users/users.json` file must contain exactly four arrays: `authorizedUsers`, `unauthorizedUsers`, `authorizedAdministrators`, and `unauthorizedAdministrators`. Account names must be valid Linux usernames; the protected `root` account is rejected. During `--apply`, authorized users and administrators are created if absent, and authorized administrators are added to `sudo`. Newly created accounts are password-locked. The users detector scores each unauthorized user and each unauthorized administrator as a separate 3-point issue. If an account appears in both unauthorized lists, unauthorized-user removal takes precedence. The users module's `fix.sh` removes unauthorized users and strips administrative group membership from unauthorized administrators without deleting those latter accounts.

## Module contract

A module is selected by its directory name in `config.json`. Both scripts are optional:

- `setup.sh` prepares the module's configured practice state. It may make system changes and therefore runs only under `--apply`.
- `detect.sh` checks the relevant condition. It must use exit code `0` only when fixed, and `1` when unresolved. Other statuses are treated as errors.

Scripts are invoked with Bash, with their module directory as the working directory. Each invocation has a 120-second timeout.

## Current implementation scope

The application provides configuration parsing, VM gating, opt-in setup execution, rendered HTML templates, a desktop launcher, and the Flask scoring API. It does not install system services, daemonize itself, or provide a general-purpose repair workflow. Additional vulnerability modules and their detection logic are maintained separately under `src/`.
