# JEOL_logger

JEOL TEM status logger for Windows. It polls read-only microscope metrics via JEOL COM, writes rotating CSV logs, and exposes a tray app for start/stop control and on-demand lens snapshots.

## What It Does

- Connects to JEOL TEM3 through type-library GUID (not ProgID-only late binding)
- Polls selected metrics on a fixed interval
- Writes compact CSV rows to keep files smaller
- Rotates files at midnight or after a configured number of hours
- Runs as a tray app with state colors:
  - blue: not logging
  - green: logging OK
  - red: logging error
- Supports on-demand lens/deflector snapshots as JSON

## Project Files

- `jeol_logger.py`: main app (tray + logger + config handling)
- `jeol_logger_config.json`: example config in repository
- `run_logger.ps1`: convenience launcher script
- `build_exe.ps1`: one-command spec-driven PyInstaller build
- `JEOL_logger.spec`: canonical PyInstaller build definition
- `requirements.txt`: Python dependencies

## Requirements

- Windows
- Python 3.8+
- JEOL TEM software installed on the instrument PC
- Python packages in `requirements.txt`

Install:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## COM Configuration

Default COM settings are embedded in the app and written to config automatically:

- `typelib_guid`: `{CE70FCE4-26D9-4BAB-9626-EC88DB7F6A0A}`
- `typelib_major`: `3`
- `typelib_minor`: `0`

The logger creates and caches TEM sub-objects once per connection (`HT3`, `GUN3`, `VACUUM3`, `Stage3`, `Lens3`, `Def3`, `EOS3`) for lower COM overhead.

Vacuum behavior:

- Penning/Pirani monitor switches are enabled at connect time.
- The app waits about 2 seconds for monitor warm-up before first read.

## Configuration File

Default config path on Windows:

- `%APPDATA%/JEOL_logger/jeol_logger_config.json`

Important keys:

- `poll_interval_seconds`: polling period in seconds
- `rotate_after_hours`: file rotation interval (`> 0` and `<= 72`)
- `log_directory`: optional override for output directory (`null` uses auto-resolution)
- `parameters_to_log`: list of metric names to log, or `"all"`
- `snapshot_directory_name`: snapshot subdirectory under `log_directory`
- `snapshot_parameters_to_log`: list of snapshot metric names, or `"all"`
- `com`: type-library settings (`typelib_guid`, `typelib_major`, `typelib_minor`)

Supported regular parameters:

- `HT actual`
- `HT setpoint`
- `Emission current`
- `Filament current`
- `Bias current`
- `Penning`
- `PiG1 Gun`
- `PiG2 Column`
- `PiG3 Specimen`
- `PiG4 Detector`
- `PiG5 RT1`
- `Stage X`
- `Stage Y`
- `Stage Z`
- `Stage TX`
- `Stage TY`

Supported snapshot parameters:

- `CL1`, `CL2`, `CL3`
- `Gun tilt X`, `Gun tilt Y`
- `Gun shift X`, `Gun shift Y`
- `Beam tilt X`, `Beam tilt Y`
- `Beam shift X`, `Beam shift Y`
- `IL1`
- `PLA X`, `PLA Y`

Example minimal config override:

```json
{
  "poll_interval_seconds": 2.0,
  "rotate_after_hours": 6,
  "parameters_to_log": ["HT actual", "Emission current", "Stage X", "Stage Y", "Stage Z"]
}
```

## Running

Tray mode (default):

```powershell
python jeol_logger.py --log-level INFO
```

Console mode:

```powershell
python jeol_logger.py --no-tray --log-level INFO
```

Single poll test:

```powershell
python jeol_logger.py --once --log-level DEBUG
```

Run without COM (for UI/file pipeline testing on non-TEM PCs):

```powershell
python jeol_logger.py --no-tray --allow-missing-com --log-level INFO
```

CLI options:

- `--config <path>`: explicit config path
- `--once`: poll once and exit
- `--log-level {DEBUG,INFO,WARNING,ERROR}`
- `--no-tray`: disable tray UI
- `--allow-missing-com`: keep running if COM connection is unavailable

## Tray Menu

- `Start Logging` / `Stop Logging`
- `Open Config`
- `Open Log Folder`
- `Create Lens Snapshot`
- `Exit`

## Log Output

Default log directory resolution on Windows when `log_directory` is `null`:

1. `%LOCALAPPDATA%/JEOL_logger/logs`
2. `%APPDATA%/JEOL_logger/logs`
3. `C:/JEOL_logging`
4. `./logs`

CSV filename pattern:

- `jeol_status_YYYYMMDD_HHMMSS.csv`

CSV columns:

- `timestamp_utc` (compact UTC format: `YYYYMMDDTHHMMSSZ`)
- `ok` (`1` for successful poll, `0` otherwise)
- `error` (exception text when poll fails)
- selected metric columns

CSV format notes:

- UTF-8 encoded plain CSV
- Compact numeric formatting to reduce size
- No fixed-width whitespace padding

Snapshot output path (default):

- `%LOCALAPPDATA%/JEOL_logger/logs/snapshots/lens_state_snapshot_YYYYMMDD_HHMMSS.json`

## Background Startup On Windows

Recommended:

1. Task Scheduler
2. NSSM/service wrapper
3. Startup script calling `run_logger.ps1`

Task Scheduler action example:

```powershell
powershell.exe -ExecutionPolicy Bypass -File "C:\path\to\JEOL_logger\run_logger.ps1" -PythonExe "C:\path\to\python.exe"
```

## Build Standalone EXE

Build (always from spec):

```powershell
python -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

This generates:

- `dist/JEOL_logger.exe`

Run EXE:

```powershell
.\dist\JEOL_logger.exe --log-level INFO
```

## Troubleshooting

- `Failed to load JEOL type library`: JEOL software/type library not installed on this PC.
- `Failed to create TEM3 COM object`: TEM software not running or COM server unavailable.
- Empty/zero vacuum values: confirm monitor switches are enabled and allow warm-up.
- Wrong parameters in tray run: update `%APPDATA%/JEOL_logger/jeol_logger_config.json` to match current app defaults.
