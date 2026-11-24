# cp-sim

cp-sim is a Linux virtual-machine-only CyberPatriot practice and scoring simulator. It organizes vulnerability modules under `src/`, optionally applies each module's simulated vulnerable-state setup, and presents detector results through a local web-based scoring report.

> **Safety requirement:** Run cp-sim only inside a disposable Linux virtual machine. The VM check is heuristic, not a guarantee. Take a VM snapshot before using `--apply` or `--fix`. The installer checks for a VM before installing system packages, but virtualization detection is not proof that a machine is disposable.

## Project specifications

1. **Target environment:** Debian/Ubuntu-based Linux virtual machines, including Ubuntu, Debian, and Linux Mint.
2. **Single entry point:** `main.sh` is the only supported entry point. It checks the VM environment, installs missing system dependencies, creates the project virtual environment, installs Python requirements, and starts the application.
3. **Application structure:** Python application code is organized in the `cp_sim/` package by responsibility. `cp_sim/__main__.py` coordinates startup; it is not intended to be invoked directly.
4. **Project modules:** Each vulnerability is represented by a subdirectory under `src/` (for example, `src/ufw/`).
5. **Configuration:** The root `config.json` selects module directories through a `vulnerabilities` array. Each entry is the name of a directory directly under `src/`.
6. **Setup scripts:** A module may contain `setup.sh`. Setup scripts never run implicitly; they execute only when the user explicitly supplies `--apply`. They prepare the configured practice state and do not run remediation scripts.
7. **Fix scripts:** A module may contain `fix.sh`. Fix scripts execute only when the user explicitly supplies `--fix`. They remediate the configured practice state. `--apply` and `--fix` are mutually exclusive.
8. **User setup policy:** The users module's `setup.sh` creates configured authorized accounts, adds them to the shared `users` group, and grants the `sudo` group only to authorized administrators. Newly created accounts have locked passwords. It does not remove or demote accounts on the deny lists.
9. **User remediation policy:** The users module's `fix.sh` removes unauthorized users and strips administrative group membership from unauthorized administrators without deleting those latter accounts. If an account appears in both unauthorized lists, unauthorized-user removal takes precedence.
10. **Generated README account lists:** When the users module is enabled, the generated desktop README displays the parsed `authorizedUsers` and `authorizedAdministrators` arrays from `src/users/users.json`.
11. **Detection scripts:** A module may contain `detect.sh`. It returns `0` when the check is fixed, `1` when unresolved, and any other status for detector errors.
12. **Module index:** At startup, populate `templates/ReadMe.html` with detected distribution information and write `~/Desktop/README.html`. An optional root-level `UserReadMe.html` is inserted as custom HTML.
13. **Scoring report:** Populate `templates/ScoringReport.html` at startup and on each report request, then write the repository-root `Scoring Report.html`. Module point values come from `properties.json` (`points`, default 1). The users module scores each distinct unauthorized user/admin finding at 3 points, with unauthorized-user removal taking precedence.
14. **Desktop shortcut:** Generate `~/Desktop/Scoring Report.desktop`. It opens `http://127.0.0.1:5000/` in the default browser; it does not start or manage Flask.
15. **Backend exposure:** Flask binds only to `127.0.0.1`; the report is intended for local access from the VM.
16. **Long-running operation:** The Flask process remains running while the scoring page is in use. System-service installation and automatic daemonization are not included.

## Repository structure

```text
.
├── main.sh                      # sole supported entry point
├── config.json                  # enabled module directory names
├── requirements.txt             # Python dependencies
├── cp_sim/
│   ├── __init__.py
│   ├── __main__.py               # startup orchestration and CLI flags
│   ├── config.py                 # paths, JSON loading, and validation
│   ├── environment.py            # VM detection and OS metadata
│   ├── modules.py                # module discovery and script execution
│   ├── scoring.py                # detector execution and scoring records
│   ├── reports.py                # HTML reports and desktop artifacts
│   └── web.py                    # Flask application and HTTP routes
├── templates/
│   ├── ReadMe.html               # generated module-index template
│   └── ScoringReport.html        # generated scoring-report template
└── src/
    ├── ufw/
    │   ├── properties.json       # UFW module metadata
    │   ├── setup.sh              # optional; only run with --apply
    │   ├── fix.sh                # optional; only run with --fix
    │   └── detect.sh             # optional; used by scoring
    └── users/
        ├── properties.json       # users module metadata
        ├── users.json            # authorized/unauthorized account lists
        ├── setup.sh              # optional; only run with --apply
        ├── fix.sh                # optional; only run with --fix
        └── detect.sh             # optional; used by scoring
```

The tree above shows the current module layout. New vulnerability modules are added as directories under `src/`; the scripts and metadata files are module-specific and may be optional unless the module's implementation requires them.

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

To explicitly prepare the configured practice state:

```bash
./main.sh --apply
```

To explicitly run module remediation scripts:

```bash
./main.sh --fix
```

The two flags are mutually exclusive. Without either flag, neither setup nor fix scripts are executed.

Do not use `--apply` or `--fix` on a host machine or a VM containing data you need to preserve. For the current UFW module, `--apply` disables UFW and `--fix` enables it.

## Using the scoring report

- The service prints its local URL: [http://127.0.0.1:5000/](http://127.0.0.1:5000/).
- Alternatively, double-click **Scoring Report** on the VM desktop. The Flask service must already be running.
- Keep the terminal running while viewing the report; closing it stops the service.
- Do not open `Scoring Report.html` directly as a local file. Each page load regenerates the report from current detector results.
- The report page refreshes periodically.

## JSON configuration files

The repository currently contains four JSON files. Their paths and complete structures are shown below.

### 1. Root `config.json`

This file selects which module directories under `src/` are loaded. Its top-level value must be one JSON object containing a `vulnerabilities` array of module directory names.

```json
{
  "vulnerabilities": [
    "ufw",
    "users"
  ]
}
```

Rules:

- Each array element must match an existing directory directly under `src/`.
- Duplicate module names and path traversal are rejected.
- The order of entries determines the configured module order.
- Add a module by adding its directory under `src/` and listing its directory name here.

### 2. `src/ufw/properties.json`

This file provides the UFW module's display name, supported distribution labels, difficulty, score value, vulnerability description, and remediation guidance.

```json
{
  "name": "Secure UFW (uncomplicated firewall)",
  "distributions": [
    "Ubuntu",
    "Debian",
    "Mint"
  ],
  "difficulty": 1,
  "points": 3,
  "vulnerability": "Misconfigured firewall can allow attackers in through backdoors.",
  "fix": "Open terminal, run \\"sudo ufw enable\\""
}
```

### 3. `src/users/properties.json`

This file provides the users module's display name, score value, vulnerability description, and remediation guidance.

```json
{
  "name": "Authorized Users and Administrators",
  "points": 3,
  "vulnerability": "Unauthorized accounts and unauthorized administrative privileges weaken system access control.",
  "fix": "Remove every unauthorized user account. For accounts listed only as unauthorized administrators, remove membership in sudo, admin, and wheel while preserving the account."
}
```

### 4. `src/users/users.json`

This file defines four arrays of Linux account names. All four keys are required:

- `authorizedUsers`: accounts that should exist and belong to the shared `users` group.
- `unauthorizedUsers`: accounts that should be removed by `--fix`.
- `authorizedAdministrators`: accounts that should exist, belong to `users`, and have `sudo` privileges.
- `unauthorizedAdministrators`: existing accounts that should lose administrative privileges but remain present.

Current file structure:

```json
{
  "authorizedUsers": [
    "bob",
    "alice",
    "jane",
    "tom"
  ],
  "unauthorizedUsers": [
    "jack",
    "tina"
  ],
  "authorizedAdministrators": [
    "bob",
    "jane"
  ],
  "unauthorizedAdministrators": [
    "alice"
  ]
}
```

Account names must be valid Linux usernames; the protected `root` account is rejected. If a name appears in both unauthorized arrays, the unauthorized-user rule takes precedence: the account is removed rather than merely demoted. The detector and scoring logic count each distinct unauthorized finding once, at 3 points per finding.

### Module `properties.json` fields

The module loader reads `properties.json` from each configured module directory. The current files demonstrate that the metadata fields can differ by module. The fields used by the application are:

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Human-readable module name |
| `points` | non-negative integer | Points assigned to the module; defaults to 1 when omitted |
| `vulnerability` | string | Description of the issue being checked |
| `fix` | string | Human-readable remediation guidance |

The UFW metadata also contains `distributions` (an array of strings) and `difficulty` (an integer). These are present in the current UFW file; they are not present in the current users file. Do not assume every module defines identical optional metadata.

## Module contract

A module is selected by its directory name in `config.json`. These scripts are optional:

- `setup.sh` prepares the module's configured practice state. It may make system changes and therefore runs only under `--apply`.
- `fix.sh` remediates the module's configured practice state. It may make system changes and therefore runs only under `--fix`.
- `detect.sh` checks the relevant condition. It must use exit code `0` only when fixed, and `1` when unresolved. Other statuses are treated as errors.

Scripts are invoked with Bash, with their module directory as the working directory. Each invocation has a 120-second timeout.

## Current implementation scope

The application provides configuration parsing, VM gating, opt-in setup and remediation execution, rendered HTML templates, a desktop launcher, and the Flask scoring API. It does not install system services, daemonize itself, or provide a general-purpose repair workflow. Additional vulnerability modules and their detection logic are maintained separately under `src/`.
