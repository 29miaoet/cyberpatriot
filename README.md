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
8. **User setup policy:** The users module's `setup.sh` creates every account listed in all four arrays in `src/users/users.json`, adds every configured account to the shared `users` group, and grants `sudo` membership to both authorized and unauthorized administrators to establish the configured practice state. Newly created accounts have locked passwords. Setup does not remove or demote accounts; remediation is exclusive to `--fix`.
9. **User remediation policy:** The users module's `fix.sh` removes unauthorized users and strips administrative group membership from unauthorized administrators without deleting those latter accounts. If an account appears in both unauthorized lists, unauthorized-user removal takes precedence.
10. **Application policy:** The applications module installs every package in both application arrays during `--apply`, creating the configured practice state. Its `--fix` script removes packages in `unauthorizedApplications` while leaving authorized packages installed.
11. **Service policy:** The services module installs and enables/starts every configured service during `--apply`, including unauthorized services to establish the practice state. Its `--fix` script stops and disables unauthorized services but leaves their packages installed. Service names map to Debian package names and systemd units as documented below.
12. **Generated README account lists:** When the users module is enabled, the generated desktop README displays the parsed `authorizedUsers` and `authorizedAdministrators` arrays from `src/users/users.json`.
13. **Detection scripts:** A module may contain `detect.sh`. It returns `0` when all its checks are fixed, `1` when one or more findings remain, and any other status for detector errors.
14. **Module index:** At startup, populate `templates/ReadMe.html` with detected distribution information and write `~/Desktop/README.html`. An optional root-level `UserReadMe.html` is inserted as custom HTML.
15. **Scoring report:** Populate `templates/ScoringReport.html` at startup and on each report request, then write the repository-root `Scoring Report.html`. Module point values come from `properties.json` (`points`, default 1). Users, applications, and services score each distinct unauthorized entry at 3 points.
16. **Desktop shortcut:** Generate `~/Desktop/Scoring Report.desktop`. It opens `http://127.0.0.1:5000/` in the default browser; it does not start or manage Flask.
17. **Backend exposure:** Flask binds only to `127.0.0.1`; the report is intended for local access from the VM.
18. **Long-running operation:** The Flask process remains running while the scoring page is in use. System-service installation and automatic daemonization are not included.

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
    ├── users/
    │   ├── properties.json       # users module metadata
    │   ├── users.json            # authorized/unauthorized account lists
    │   ├── setup.sh              # only run with --apply
    │   ├── fix.sh                # only run with --fix
    │   └── detect.sh             # used by scoring
    ├── applications/
    │   ├── properties.json       # application module metadata
    │   ├── applications.json     # authorized/unauthorized APT packages
    │   ├── setup.sh              # installs configured packages with --apply
    │   ├── fix.sh                # removes unauthorized packages with --fix
    │   └── detect.sh             # checks unauthorized package presence
    ├── services/
    │   ├── properties.json       # service module metadata
    │   ├── services.json         # authorized/unauthorized service names
    │   ├── setup.sh              # installs, enables, and starts with --apply
    │   ├── fix.sh                # stops/disables unauthorized services with --fix
    │   └── detect.sh             # checks unauthorized service state
    ├── common.sh                 # shared helpers for module scripts
    ├── apt_updates/              # pending APT package updates
    ├── automatic_updates/        # periodic APT and unattended upgrades
    ├── root_password_lock/       # root password account lock
    ├── password_min_length/      # PAM minimum password length
    ├── password_history/         # PAM password history
    ├── null_passwords/           # PAM null-password authentication
    ├── shadow_permissions/       # /etc/shadow mode
    ├── grub_permissions/         # GRUB configuration mode
    ├── ssh_root_login/           # SSH root login policy
    ├── ssh_blank_passwords/      # SSH empty-password policy
    ├── tcp_syncookies/           # TCP SYN cookies sysctl
    ├── address_space_randomization/ # ASLR sysctl
    ├── ipv4_forwarding/          # IPv4 forwarding sysctl
    ├── tcp_rfc1337/              # TCP TIME-WAIT protection sysctl
    ├── passwordless_sudo/        # sudoers NOPASSWD policy
    ├── password_min_age/         # default minimum password age
    ├── password_max_age/         # human-user maximum password age
    ├── snap_updates/             # optional Snap package updates
    └── lightdm_guest/            # optional LightDM guest-session policy
```

The tree above shows the current module layout. New vulnerability modules are added as directories under `src/`; the scripts and metadata files are module-specific and may be optional unless the module's implementation requires them.

Generated at runtime in the VM:

- `Scoring Report.html` in the repository root
- `~/Desktop/README.html` — configured module index
- `~/Desktop/Answer Key.md` — vulnerability descriptions and remediation guidance
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

Do not use `--apply` or `--fix` on a host machine or a VM containing data you need to preserve. For the current UFW module, `--apply` disables UFW and `--fix` enables it. The services module starts every configured service during `--apply`, including unauthorized network services such as Postfix and Apache. Run the practice VM on an isolated virtual network; do not expose these services to a public network or a trusted LAN.

## Using the scoring report

- The service prints its local URL: [http://127.0.0.1:5000/](http://127.0.0.1:5000/).
- Alternatively, double-click **Scoring Report** on the VM desktop. The Flask service must already be running.
- Keep the terminal running while viewing the report; closing it stops the service.
- Do not open `Scoring Report.html` directly as a local file. Each page load regenerates the report from current detector results.
- The report automatically refreshes every 5 seconds. Each refresh reruns the read-only detectors; it does not run setup or remediation scripts.
- The report lists only scored issues that have been fixed and earned points. Unresolved issues and checks that have not been fixed are omitted. If no scored issues have been fixed, the issues section is left empty. Vulnerability descriptions and remediation guidance are kept separately in `~/Desktop/Answer Key.md`.

## JSON configuration files

The original account, application, and service configuration files are documented below. Each independently scored checklist module also has its own `properties.json`.

### 1. Root `config.json`

This file selects the module directories under `src/`. Its top-level value must be one JSON object containing a `vulnerabilities` array of unique directory names.

```json
{
  "vulnerabilities": [
    "ufw",
    "users",
    "applications",
    "services",
    "apt_updates",
    "automatic_updates",
    "root_password_lock",
    "password_min_length",
    "password_history",
    "null_passwords",
    "shadow_permissions",
    "grub_permissions",
    "ssh_root_login",
    "ssh_blank_passwords",
    "tcp_syncookies",
    "address_space_randomization",
    "ipv4_forwarding",
    "tcp_rfc1337",
    "passwordless_sudo",
    "password_min_age",
    "password_max_age"
  ]
}
```

Every entry must match an existing directory directly under `src/`. Duplicate names and path traversal are rejected. The array order determines module execution and report order.

### 2. `src/ufw/properties.json`

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
  "fix": "Open terminal, run \"sudo ufw enable\"",
  "fixedMessage": "UFW (uncomplicated firewall) is enabled"
}
```

### 3. `src/users/properties.json`

```json
{
  "name": "Authorized Users and Administrators",
  "points": 3,
  "vulnerability": "Unauthorized accounts and unauthorized administrative privileges weaken system access control.",
  "fix": "Remove every unauthorized user account. For accounts listed only as unauthorized administrators, remove membership in sudo, admin, and wheel while preserving the account."
}
```

### 4. `src/users/users.json`

This file contains exactly four arrays of Linux account names:

- `authorizedUsers`: accounts that should exist and belong to the shared `users` group.
- `unauthorizedUsers`: accounts created in the practice state and removed by `--fix`.
- `authorizedAdministrators`: accounts that should exist, belong to `users`, and have `sudo` privileges.
- `unauthorizedAdministrators`: accounts created with administrative privileges in the practice state; `--fix` removes those privileges but preserves the accounts.

```json
{
  "authorizedUsers": ["bob", "alice", "jane", "tom"],
  "unauthorizedUsers": ["jack", "tina"],
  "authorizedAdministrators": ["bob", "jane"],
  "unauthorizedAdministrators": ["alice"]
}
```

Account names must be valid Linux usernames; the protected `root` account is rejected. An account in both unauthorized arrays is treated as an unauthorized user and removed rather than merely demoted.

### 5. `src/applications/properties.json`

```json
{
  "name": "Authorized and Unauthorized Applications",
  "points": 3,
  "vulnerability": "Unapproved software increases the attack surface and may violate system-use policy.",
  "fix": "Remove every installed application listed in unauthorizedApplications while preserving authorized applications."
}
```

### 6. `src/applications/applications.json`

This file contains exactly two arrays of Debian package names:

- `authorizedApplications`: packages that should be installed and retained.
- `unauthorizedApplications`: packages installed by `--apply` to create the practice state and removed by `--fix`.

```json
{
  "authorizedApplications": [
    "wireshark"
  ],
  "unauthorizedApplications": [
    "ophcrack",
    "nmap",
    "zangband"
  ]
}
```

These values are APT package names, not display names or executable paths. The setup script installs all listed packages, including unauthorized ones, so that the detector can identify them. The fix script runs APT removal only for unauthorized packages; it does not purge package configuration or automatically remove dependencies. A package must be available from the VM's configured APT repositories for setup to succeed. In particular, `ophcrack` is in Ubuntu's `universe` component, while `zangband` is in Ubuntu's `multiverse` component and Debian's `non-free` component. Ensure the relevant component is already enabled in the VM, or remove that package from the configured list before running `--apply`.

### 7. `src/services/properties.json`

```json
{
  "name": "Authorized and Unauthorized Services",
  "points": 3,
  "vulnerability": "Unapproved network services expose unnecessary listening endpoints and increase the system attack surface.",
  "fix": "Stop and disable every service listed in unauthorizedServices. Keep its package installed so the account and service policy can be reviewed independently."
}
```

### 8. `src/services/services.json`

This file contains exactly two arrays of supported service identifiers:

- `authorizedServices`: services that should be installed, enabled, and running.
- `unauthorizedServices`: services enabled and started by `--apply` to create the practice state, then stopped and disabled by `--fix`.

```json
{
  "authorizedServices": [
    "ssh",
    "vsftpd"
  ],
  "unauthorizedServices": [
    "postfix",
    "apache2"
  ]
}
```

The service module currently accepts these identifiers and maps them to Debian packages and systemd units:

| JSON identifier | APT package | systemd unit | Description |
|---|---|---|---|
| `ssh` | `openssh-server` | `ssh.service` | OpenSSH server |
| `vsftpd` | `vsftpd` | `vsftpd.service` | FTP server |
| `postfix` | `postfix` | `postfix.service` | SMTP mail-transfer service |
| `apache2` | `apache2` | `apache2.service` | Apache HTTP server |

SMTP is a mail-transfer protocol, not a specific systemd service name. In this configuration, `postfix` is the concrete SMTP server implementation. Do not put the generic string `smtp` in the arrays; use a supported service identifier. The module requires systemd and uses the listed Debian package/unit mappings.

During `--apply`, every configured service is installed and enabled/started, including unauthorized services. During `--fix`, unauthorized services are stopped and disabled but their packages remain installed. The detector reports an unauthorized service if it is active **or** enabled.

### Additional independently scored checklist modules

Each enabled checklist module below has its own `properties.json`, `setup.sh`, `fix.sh`, and `detect.sh`. Point values are assigned per module on a 1–3 scale according to the relative impact of the setting; they can be adjusted independently in that module's metadata.

| Module directory | Check | Points |
|---|---|---:|
| `apt_updates` | Pending APT package upgrades | 3 |
| `automatic_updates` | APT periodic list refresh and unattended upgrades | 2 |
| `root_password_lock` | Root account password lock | 3 |
| `password_min_length` | PAM minimum password length of 10 | 2 |
| `password_history` | PAM remembers the previous three passwords | 2 |
| `null_passwords` | PAM does not allow null passwords | 3 |
| `shadow_permissions` | `/etc/shadow` permissions are 0600 | 2 |
| `grub_permissions` | `/boot/grub/grub.cfg` permissions are 0600 | 2 |
| `ssh_root_login` | Effective SSH policy sets `PermitRootLogin no` | 3 |
| `ssh_blank_passwords` | Effective SSH policy sets `PermitEmptyPasswords no` | 3 |
| `tcp_syncookies` | `net.ipv4.tcp_syncookies=1` | 2 |
| `address_space_randomization` | `kernel.randomize_va_space=2` | 2 |
| `ipv4_forwarding` | `net.ipv4.ip_forward=0` | 2 |
| `tcp_rfc1337` | `net.ipv4.tcp_rfc1337=1` | 1 |
| `passwordless_sudo` | No active `NOPASSWD:` sudoers tags | 3 |
| `password_min_age` | New-account default `PASS_MIN_DAYS=2` | 1 |
| `password_max_age` | Interactive user passwords expire after at most 90 days | 2 |
| `snap_updates` | Installed Snap package refreshes (opt-in) | 1 |
| `lightdm_guest` | LightDM guest sessions disabled (opt-in) | 1 |

Two additional modules are available but intentionally not enabled in the default `config.json`: `snap_updates` (enable it only on systems using Snap) and `lightdm_guest` (enable it only when LightDM is installed). The latter checks the effective `lightdm --show-config` output. Snap's update detector treats a system without Snap as not applicable.

The following checklist items are deliberately not automated: normalizing APT repositories across Debian/Ubuntu/Mint (source formats, release codenames, and repository components differ); Mint Update Manager GUI workflows; FTP configuration; arbitrary user additions or password changes without team-specific account data; PAM faillock because the supplied stack fragments do not establish a complete distribution-safe policy; global umask enforcement; and forensic removal of suspicious directories, processes, cron entries, media/archive files, backdoors, or reverse shells. These require environment-specific review and should not be converted into broad automatic deletion or process-killing rules. Existing `users`, `applications`, and `services` modules continue to handle their explicitly configured entries.

**Implementation notes:** Password history is implemented with `pam_pwhistory.so remember=3 use_authtok`, the dedicated PAM password-history module. The checklist's `chage -m 90` example sets a minimum interval; the 90-day maximum implied by its `/etc/shadow` example is implemented with `chage -M 90`. The maximum-age module applies to interactive accounts with UID ≥1000, excluding UID 65534 and non-login shells. The SSH scripts validate the configuration but do not reload SSH. IPv4 forwarding is disabled by default in this policy; do not enable that module on a machine intentionally acting as a router.

### Module JSON rules

- Each module configuration file must contain exactly the keys shown for that file.
- Every list must be a JSON array of strings with no duplicates.
- An item cannot appear in both the authorized and unauthorized arrays of the same module.
- Application entries must be valid Debian package-name strings.
- Service entries must match one of the four supported identifiers in the mapping table.
- Each unauthorized user, application, or service is scored independently for 3 points. A finding is fixed when its detector no longer reports it.

### Module `properties.json` fields

The module loader reads `properties.json` from each configured module directory. The current files demonstrate that the metadata fields can differ by module. The fields used by the application are:

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Human-readable module name |
| `points` | non-negative integer | Points assigned to the module; defaults to 1 when omitted |
| `vulnerability` | string | Description of the issue being checked |
| `fix` | string | Human-readable remediation guidance |
| `fixedMessage` | string | Optional report message displayed when the module's check is fixed |

The UFW metadata also contains `distributions` (an array of strings) and `difficulty` (an integer). These are present in the current UFW file; they are not present in the current users file. Do not assume every module defines identical optional metadata.

## Module contract

A module is selected by its directory name in `config.json`. These scripts are optional:

- `setup.sh` prepares the module's configured practice state. It may make system changes and therefore runs only under `--apply`.
- `fix.sh` remediates the module's configured practice state. It may make system changes and therefore runs only under `--fix`.
- `detect.sh` checks the relevant condition. It must use exit code `0` only when fixed, and `1` when unresolved. Other statuses are treated as errors.

Scripts are invoked with Bash, with their module directory as the working directory. Each invocation has a 120-second timeout.

## Current implementation scope

The application provides configuration parsing, VM gating, opt-in setup and remediation execution, rendered HTML templates, a desktop launcher, and the Flask scoring API. It does not install system services, daemonize itself, or provide a general-purpose repair workflow. Each checklist vulnerability is independently configured under `src/` and uses the generic module scoring path.
