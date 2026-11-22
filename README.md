# cp-sim

cp-sim is a Linux virtual-machine-only CyberPatriot practice and scoring simulator. It organizes vulnerability modules under `src/`, optionally applies each module's simulated vulnerable-state setup, and presents detector results through a local web-based scoring report.

> **Safety requirement:** Run cp-sim only inside a disposable Linux virtual machine. The VM check is heuristic, not a guarantee. Take a VM snapshot before using `--apply`.

## Project specifications

These specifications consolidate the requirements established in the project-planning prompts:

1. **Target environment:** Linux virtual machines only. The application refuses to run when it cannot positively identify a supported VM environment.
2. **Project structure:** Each vulnerability is represented by a subdirectory under `src/` (for example, `src/ufw/`).
3. **Configuration:** The root `config.json` is one JSON object with a single `vulnerabilities` array. Each array element is the name of a directory directly under `src/`.
4. **Setup scripts:** A module may contain `setup.sh`. Setup scripts never run implicitly; they execute only when the user explicitly supplies `--apply`.
5. **Detection scripts:** A module may contain `detect.sh`. It returns:
   - `0`: the check is fixed;
   - `1`: the check remains unresolved;
   - any other exit status: detector error.
6. **Module index:** At startup, generate `~/Desktop/README.html` in the VM, listing the configured module directories.
7. **Scoring report:** Generate root-level `Scoring Report.html`. Its JavaScript polls the Flask backend and displays successful checks (for example, “UFW has been enabled”). Unresolved checks are omitted; detector errors are reported separately.
8. **Backend exposure:** Flask binds only to `127.0.0.1`; the report is intended for local access from the VM.
9. **Long-running operation:** The Flask process remains running while the scoring page is in use. System-service installation and automatic daemonization are not part of the initial implementation.

## Repository layout

```text
.
├── main.py
├── config.json
├── requirements.txt
├── README.md
├── Scoring Report.html       # generated at runtime
└── src/
    └── <module>/
        ├── setup.sh          # optional; only run with --apply
        └── detect.sh         # optional; checked by the scoring API
```

## Configuration

Edit `config.json` to select module directories:

```json
{
  "vulnerabilities": [
    "ufw"
  ]
}
```

Names must refer to existing directories directly inside `src/`. Duplicate names and path traversal are rejected.

## Installation

From the repository root, inside the Linux VM:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Running

Read-only startup (does not execute setup scripts):

```bash
python main.py
```

Explicitly apply configured setup scripts, then start the scoring service:

```bash
python main.py --apply
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/) inside the VM. The scoring page refreshes detector results every five seconds. The generated module index is written to `~/Desktop/README.html`.

## Module contract

A module is selected by its directory name in `config.json`. Both scripts are optional:

- `setup.sh` prepares the module's configured practice state. It may make system changes and therefore runs only under `--apply`.
- `detect.sh` checks the relevant condition. It must use exit code `0` only when the condition is fixed, and `1` when it is not fixed. Other statuses are treated as errors.

Scripts are invoked with Bash, with their module directory as the working directory. Each invocation has a 120-second timeout.

## Current implementation scope

The initial implementation provides configuration parsing, VM gating, opt-in setup execution, generated HTML reports, and the Flask scoring API. It does not install system services, daemonize itself, or provide a general-purpose repair/fix workflow. Additional vulnerability modules and their detection logic are maintained separately under `src/`.
