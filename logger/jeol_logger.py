#!/usr/bin/env python3
"""JEOL TEM status logger.

This script polls read-only metrics from a JEOL microscope through COM and
writes rolling CSV log files for downstream plotting/analysis tools.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


LOGGER = logging.getLogger("jeol_logger")
MAX_ROTATE_HOURS = 72.0
DEFAULT_CONFIG_FILENAME = "jeol_logger_config.json"


# JEOL TEM3 COM type-library GUID and version (same as beam_blank_comtypes.py)
JEOL_TYPELIB_GUID = "{CE70FCE4-26D9-4BAB-9626-EC88DB7F6A0A}"
JEOL_TYPELIB_MAJOR = 3
JEOL_TYPELIB_MINOR = 0


@dataclass
class COMSettings:
    typelib_guid: str = JEOL_TYPELIB_GUID
    typelib_major: int = JEOL_TYPELIB_MAJOR
    typelib_minor: int = JEOL_TYPELIB_MINOR


DEFAULT_COM_SETTINGS = COMSettings()


@dataclass
class MetricDefinition:
    name: str
    path: str


KNOWN_PARAMETER_PATHS: Dict[str, str] = {
    "HT actual": "gun3.GetHtCurrentValue()[0]",
    "HT setpoint": "ht3.GetHtValue()[0]",
    "Emission current": "gun3.GetEmissionCurrentValue()[0]",
    "Filament current": "gun3.GetFilamentCurrentValue()[0]",
    "Bias current": "gun3.GetBiasCurrentValue()[0]",
    "Penning": "vacuum3.GetPenningInfo(0)[0]",
    "PiG1 Gun": "vacuum3.GetPiraniInfo(0)[0]",
    "PiG2 Column": "vacuum3.GetPiraniInfo(1)[0]",
    "PiG3 Specimen": "vacuum3.GetPiraniInfo(2)[0]",
    "PiG4 Detector": "vacuum3.GetPiraniInfo(3)[0]",
    "PiG5 RT1": "vacuum3.GetPiraniInfo(4)[0]",
    "Stage X": "stage3.GetPos()[0]",
    "Stage Y": "stage3.GetPos()[1]",
    "Stage Z": "stage3.GetPos()[2]",
    "Stage TX": "stage3.GetPos()[3]",
    "Stage TY": "stage3.GetPos()[4]",
}

AVAILABLE_PARAMETERS: List[str] = list(KNOWN_PARAMETER_PATHS.keys())


@dataclass
class LoggerSettings:
    poll_interval_seconds: float
    log_directory: str
    rotate_after_hours: float
    com: COMSettings
    metrics: List[MetricDefinition]
    snapshot_directory_name: str
    snapshot_metrics: List[MetricDefinition]


class ShutdownSignal:
    def __init__(self) -> None:
        self.stop = False

    def request_stop(self, _sig: int, _frame: Any) -> None:
        self.stop = True


class COMClient:
    """Manages the JEOL TEM3 COM connection and cached sub-objects."""

    def __init__(self, settings: COMSettings) -> None:
        self.settings = settings
        self._obj: Any = None
        self.ht3: Any = None
        self.gun3: Any = None
        self.vacuum3: Any = None
        self.stage3: Any = None
        self.lens3: Any = None
        self.def3: Any = None
        self.eos3: Any = None

    def connect(self) -> None:
        try:
            import comtypes  # type: ignore
            import comtypes.client  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "comtypes is required. Install with: pip install comtypes"
            ) from exc

        guid = self.settings.typelib_guid
        major = self.settings.typelib_major
        minor = self.settings.typelib_minor

        try:
            temext = comtypes.client.GetModule((guid, major, minor))
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load JEOL type library (GUID={guid}, "
                f"v{major}.{minor}). Is the JEOL TEM software installed?"
            ) from exc

        try:
            self._obj = comtypes.client.CreateObject(
                temext.TEM3, comtypes.CLSCTX_ALL
            )
            LOGGER.info(
                "Connected to JEOL TEM3 via type-library GUID %s v%d.%d",
                guid, major, minor,
            )
        except OSError as exc:
            raise RuntimeError(
                f"Failed to create TEM3 COM object (GUID={guid}). "
                "Is the JEOL TEM software running?"
            ) from exc

        self._create_sub_objects()
        self._enable_vacuum_monitors()

    def _create_sub_objects(self) -> None:
        """Create all COM sub-objects once and cache them."""
        self.ht3 = self._obj.CreateHT3()
        self.gun3 = self._obj.CreateGUN3()
        self.vacuum3 = self._obj.CreateVACUUM3()
        self.stage3 = self._obj.CreateStage3()
        self.lens3 = self._obj.CreateLens3()
        self.def3 = self._obj.CreateDef3()
        self.eos3 = self._obj.CreateEOS3()
        LOGGER.info("Created TEM sub-objects: ht3, gun3, vacuum3, stage3, lens3, def3, eos3")

    def read_metric(self, metric_path: str) -> Any:
        if self._obj is None:
            raise RuntimeError("COM object is not connected")
        return resolve_path(self, metric_path)

    def _enable_vacuum_monitors(self) -> None:
        """Enable Penning and Pirani gauge monitoring.

        The JEOL COM interface requires these switches to be turned on
        before GetPenningInfo / GetPiraniInfo return live values.
        A ~2 s warm-up is needed before the first readings are valid.
        """
        try:
            self.vacuum3.SetPenningMonitorSw(1)
            self.vacuum3.SetPiraniMonitorSw(1)
            time.sleep(2)
            LOGGER.info("Enabled Penning and Pirani vacuum monitors")
        except Exception:
            LOGGER.warning("Could not enable vacuum monitors", exc_info=True)


KNOWN_SNAPSHOT_PATHS: Dict[str, str] = {
    "CL1": "lens3.GetCL1()[0]",
    "CL2": "lens3.GetCL2()[0]",
    "CL3": "lens3.GetCL3()[0]",
    "Gun tilt X": "def3.GetGunA2()[0]",
    "Gun tilt Y": "def3.GetGunA2()[1]",
    "Gun shift X": "def3.GetGunA1()[0]",
    "Gun shift Y": "def3.GetGunA1()[1]",
    "Beam tilt X": "def3.GetCLA2()[0]",
    "Beam tilt Y": "def3.GetCLA2()[1]",
    "Beam shift X": "def3.GetCLA1()[0]",
    "Beam shift Y": "def3.GetCLA1()[1]",
    "IL1": "lens3.GetIL1()[0]",
    "PLA X": "def3.GetPLA()[0]",
    "PLA Y": "def3.GetPLA()[1]",
}

AVAILABLE_SNAPSHOT_PARAMETERS: List[str] = list(KNOWN_SNAPSHOT_PATHS.keys())


DEFAULT_CONFIG: Dict[str, Any] = {
    "poll_interval_seconds": 2.0,
    "log_directory": None,
    "rotate_after_hours": 24.0,
    "available_parameters": AVAILABLE_PARAMETERS,
    "parameters_to_log": AVAILABLE_PARAMETERS,
    "snapshot_directory_name": "snapshots",
    "available_snapshot_parameters": AVAILABLE_SNAPSHOT_PARAMETERS,
    "snapshot_parameters_to_log": AVAILABLE_SNAPSHOT_PARAMETERS,
}


class LogWriter:
    def __init__(self, directory: pathlib.Path, rotate_after_hours: float, metric_names: List[str]) -> None:
        self.directory = directory
        self.rotate_after = dt.timedelta(hours=rotate_after_hours)
        self.metric_names = metric_names

        self.directory.mkdir(parents=True, exist_ok=True)

        self._file_handle: Optional[Any] = None
        self._writer: Optional[csv.DictWriter] = None
        self._opened_at: Optional[dt.datetime] = None
        self._opened_date: Optional[dt.date] = None

    def _should_rotate(self, now: dt.datetime) -> bool:
        if self._opened_at is None or self._opened_date is None:
            return True
        if (now - self._opened_at) >= self.rotate_after:
            return True
        if now.date() != self._opened_date:
            return True
        return False

    def _new_file_path(self, now: dt.datetime) -> pathlib.Path:
        stamp = now.strftime("%Y%m%d_%H%M%S")
        return self.directory / f"jeol_status_{stamp}.csv"

    def _open_new_file(self, now: dt.datetime) -> None:
        if self._file_handle:
            self._file_handle.close()

        path = self._new_file_path(now)
        self._file_handle = path.open("w", newline="", encoding="utf-8")

        self._fieldnames = ["timestamp_utc", "ok", "error"] + self.metric_names
        self._writer = None  # we handle formatting ourselves
        self._write_header()
        self._file_handle.flush()

        self._opened_at = now
        self._opened_date = now.date()
        LOGGER.info("Opened new log file: %s", path)

    def write_row(self, row: Dict[str, Any], now: dt.datetime) -> None:
        if self._should_rotate(now):
            self._open_new_file(now)

        assert self._file_handle is not None
        values = [self._fmt(row.get(f, "")) for f in self._fieldnames]
        self._file_handle.write(",".join(values) + "\n")
        self._file_handle.flush()

    def _write_header(self) -> None:
        self._file_handle.write(",".join(self._fieldnames) + "\n")

    @staticmethod
    def _fmt(value: Any) -> str:
        if isinstance(value, float):
            if value == 0.0:
                return "0"
            if abs(value) >= 1000 or abs(value) < 0.01:
                s = f"{value:.4e}"
                # strip trailing zeros from mantissa: 2.0000e+05 -> 2e+05
                m, e = s.split("e")
                m = m.rstrip("0").rstrip(".")
                return f"{m}e{e}"
            return f"{value:g}"
        return str(value)

    def close(self) -> None:
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
            self._writer = None


import re as _re

_METHOD_RE = _re.compile(r"^(\w+)\(([^)]*)\)$")


def resolve_path(root: Any, path_expr: str) -> Any:
    """Resolve dotted COM path expressions.

    Supported forms for each segment:
    - Attribute access: Stage
    - Zero-arg method call: GetHTValue()
    - Method call with int args: GetPenningInfo(0)
    - Indexed access: result[0]
    """

    current = root
    for part in path_expr.split("."):
        part = part.strip()
        if not part:
            raise ValueError(f"Invalid path: '{path_expr}'")

        index: Optional[int] = None
        core = part
        if part.endswith("]") and "[" in part:
            core, idx_str = part[:-1].rsplit("[", 1)
            index = int(idx_str)

        m = _METHOD_RE.match(core)
        if m:
            method_name = m.group(1)
            args_str = m.group(2).strip()
            method = getattr(current, method_name)
            if args_str:
                args = [int(a.strip()) for a in args_str.split(",")]
                current = method(*args)
            else:
                current = method()
        elif core:
            current = getattr(current, core)
        else:
            raise ValueError(f"Invalid path segment: '{part}'")

        if index is not None:
            current = current[index]

    return normalize_value(current)


def normalize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    for attr in ("value", "Value"):
        if hasattr(value, attr):
            try:
                candidate = getattr(value, attr)
                if not callable(candidate):
                    return candidate
            except Exception:
                pass

    return str(value)


def _is_dir_writable(path: pathlib.Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def resolve_log_directory(configured_value: Optional[str]) -> pathlib.Path:
    if configured_value:
        return pathlib.Path(configured_value)

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            preferred = pathlib.Path(local_app_data) / "JEOL_logger" / "logs"
            if _is_dir_writable(preferred):
                return preferred

        app_data = os.environ.get("APPDATA")
        if app_data:
            secondary = pathlib.Path(app_data) / "JEOL_logger" / "logs"
            if _is_dir_writable(secondary):
                return secondary

        preferred = pathlib.Path("C:/JEOL_logging")
        if _is_dir_writable(preferred):
            return preferred

    return pathlib.Path("logs")


def resolve_config_path(config_arg: Optional[str]) -> pathlib.Path:
    if config_arg:
        return pathlib.Path(config_arg)

    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return pathlib.Path(app_data) / "JEOL_logger" / DEFAULT_CONFIG_FILENAME

    return pathlib.Path(DEFAULT_CONFIG_FILENAME)


def ensure_config_exists(config_path: pathlib.Path) -> None:
    if config_path.exists():
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    LOGGER.info("Created default config: %s", config_path)


def build_metrics_from_config(config: Dict[str, Any]) -> List[MetricDefinition]:
    metric_paths = dict(KNOWN_PARAMETER_PATHS)

    selected = config.get("parameters_to_log", "all")
    if selected == "all":
        selected_names = list(metric_paths.keys())
    elif isinstance(selected, list):
        selected_names = [str(name) for name in selected]
    else:
        raise ValueError("parameters_to_log must be 'all' or a list of parameter names")

    unknown = [name for name in selected_names if name not in metric_paths]
    if unknown:
        raise ValueError(
            "Unknown parameter name(s): "
            + ", ".join(unknown)
            + ". Use only names from available_parameters."
        )

    return [MetricDefinition(name=name, path=metric_paths[name]) for name in selected_names]


def build_snapshot_metrics_from_config(config: Dict[str, Any]) -> List[MetricDefinition]:
    snapshot_paths = dict(KNOWN_SNAPSHOT_PATHS)

    selected = config.get("snapshot_parameters_to_log", "all")
    if selected == "all":
        selected_names = list(snapshot_paths.keys())
    elif isinstance(selected, list):
        selected_names = [str(name) for name in selected]
    else:
        raise ValueError("snapshot_parameters_to_log must be 'all' or a list of names")

    unknown = [name for name in selected_names if name not in snapshot_paths]
    if unknown:
        raise ValueError(
            "Unknown snapshot parameter name(s): "
            + ", ".join(unknown)
            + ". Use only names from available_snapshot_parameters."
        )

    return [MetricDefinition(name=name, path=snapshot_paths[name]) for name in selected_names]


def load_settings(path: pathlib.Path) -> LoggerSettings:
    config = json.loads(path.read_text(encoding="utf-8"))

    com_cfg = config.get("com", {})
    metrics = build_metrics_from_config(config)
    snapshot_metrics = build_snapshot_metrics_from_config(config)
    rotate_after_hours = float(config.get("rotate_after_hours", 24.0))

    if rotate_after_hours <= 0:
        raise ValueError("rotate_after_hours must be greater than 0")
    if rotate_after_hours > MAX_ROTATE_HOURS:
        raise ValueError(f"rotate_after_hours must be <= {MAX_ROTATE_HOURS}")

    resolved_log_directory = resolve_log_directory(config.get("log_directory"))

    return LoggerSettings(
        poll_interval_seconds=float(config.get("poll_interval_seconds", 2.0)),
        log_directory=str(resolved_log_directory),
        rotate_after_hours=rotate_after_hours,
        snapshot_directory_name=str(config.get("snapshot_directory_name", "snapshots")),
        com=COMSettings(
            typelib_guid=str(com_cfg.get("typelib_guid", DEFAULT_COM_SETTINGS.typelib_guid)),
            typelib_major=int(com_cfg.get("typelib_major", DEFAULT_COM_SETTINGS.typelib_major)),
            typelib_minor=int(com_cfg.get("typelib_minor", DEFAULT_COM_SETTINGS.typelib_minor)),
        ),
        metrics=metrics,
        snapshot_metrics=snapshot_metrics,
    )


def build_row(timestamp_utc: dt.datetime, metrics: Dict[str, Any], ok: bool, error: str) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "timestamp_utc": timestamp_utc.strftime("%Y%m%dT%H%M%SZ"),
        "ok": int(ok),
        "error": error,
    }
    row.update(metrics)
    return row


def run_logger(
    settings: LoggerSettings,
    run_once: bool = False,
    stop_event: Optional[threading.Event] = None,
    allow_missing_com: bool = False,
    on_poll: Optional[Callable[[bool, str], None]] = None,
) -> int:
    shutdown = ShutdownSignal()
    owns_stop_event = stop_event is None
    if owns_stop_event:
        stop_event = threading.Event()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, shutdown.request_stop)
        signal.signal(signal.SIGTERM, shutdown.request_stop)

    metric_names = [m.name for m in settings.metrics]
    writer = LogWriter(
        directory=pathlib.Path(settings.log_directory),
        rotate_after_hours=settings.rotate_after_hours,
        metric_names=metric_names,
    )

    client = COMClient(settings.com)
    connection_error = ""
    try:
        client.connect()
    except Exception as exc:
        connection_error = f"{type(exc).__name__}: {exc}"
        if not allow_missing_com:
            LOGGER.exception("Failed to connect to COM server")
            return 2
        LOGGER.warning("Starting without COM connection: %s", connection_error)

    interval = max(settings.poll_interval_seconds, 0.2)

    try:
        while not shutdown.stop and not stop_event.is_set():
            loop_start = dt.datetime.now(dt.timezone.utc)
            ok = True
            error = ""
            values: Dict[str, Any] = {name: "" for name in metric_names}

            if connection_error:
                ok = False
                error = connection_error
            else:
                try:
                    for metric in settings.metrics:
                        values[metric.name] = client.read_metric(metric.path)
                except Exception as exc:
                    ok = False
                    error = f"{type(exc).__name__}: {exc}"
                    LOGGER.warning("Metric read failed: %s", error)

            if on_poll is not None:
                on_poll(ok, error)

            writer.write_row(
                build_row(timestamp_utc=loop_start, metrics=values, ok=ok, error=error),
                now=loop_start.astimezone(),
            )

            if run_once:
                break

            elapsed = (dt.datetime.now(dt.timezone.utc) - loop_start).total_seconds()
            sleep_for = max(0.0, interval - elapsed)
            time.sleep(sleep_for)

    finally:
        writer.close()
        if owns_stop_event:
            stop_event.set()

    return 0


def create_snapshot(settings: LoggerSettings) -> pathlib.Path:
    log_dir = pathlib.Path(settings.log_directory)
    snapshot_dir = log_dir / settings.snapshot_directory_name
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now(dt.timezone.utc)
    out_path = snapshot_dir / f"lens_state_snapshot_{now.strftime('%Y%m%d_%H%M%S')}.json"

    client = COMClient(settings.com)
    client.connect()

    values: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    for metric in settings.snapshot_metrics:
        try:
            values[metric.name] = client.read_metric(metric.path)
        except Exception as exc:
            errors[metric.name] = f"{type(exc).__name__}: {exc}"

    payload = {
        "timestamp_utc": now.isoformat(timespec="seconds"),
        "com_typelib_guid": settings.com.typelib_guid,
        "ok": len(errors) == 0,
        "values": values,
        "errors": errors,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


class LoggerController:
    def __init__(self, config_path: pathlib.Path, allow_missing_com: bool = False) -> None:
        self.config_path = config_path
        self.allow_missing_com = allow_missing_com
        self._lock = threading.Lock()
        self._stop_event: Optional[threading.Event] = None
        self._thread: Optional[threading.Thread] = None
        self._last_poll_ok: Optional[bool] = None
        self._last_poll_error: str = ""
        self._thread_crashed: bool = False

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def state(self) -> str:
        """Return 'idle', 'logging', or 'error'."""
        if not self.is_running:
            return "idle"
        if self._thread_crashed or self._last_poll_ok is False:
            return "error"
        return "logging"

    def _on_poll(self, ok: bool, error: str) -> None:
        self._last_poll_ok = ok
        self._last_poll_error = error

    def start_logging(self) -> None:
        with self._lock:
            if self.is_running:
                return

            settings = load_settings(self.config_path)
            stop_event = threading.Event()

            self._last_poll_ok = None
            self._last_poll_error = ""
            self._thread_crashed = False

            def _runner() -> None:
                try:
                    run_logger(
                        settings=settings,
                        run_once=False,
                        stop_event=stop_event,
                        allow_missing_com=self.allow_missing_com,
                        on_poll=self._on_poll,
                    )
                except Exception:
                    LOGGER.exception("Logging thread terminated unexpectedly")
                    self._thread_crashed = True

            thread = threading.Thread(target=_runner, name="jeol-logger", daemon=True)
            thread.start()
            self._stop_event = stop_event
            self._thread = thread
            LOGGER.info("Logging started")

    def stop_logging(self) -> None:
        with self._lock:
            stop_event = self._stop_event
            thread = self._thread
            self._stop_event = None
            self._thread = None

        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join(timeout=10)
        LOGGER.info("Logging stopped")

    def toggle_logging(self) -> None:
        if self.is_running:
            self.stop_logging()
        else:
            self.start_logging()

    def open_config_file(self) -> None:
        path = self.config_path.resolve()
        self._open_path(path)

    def open_log_folder(self) -> None:
        try:
            settings = load_settings(self.config_path)
            log_path = pathlib.Path(settings.log_directory).resolve()
            log_path.mkdir(parents=True, exist_ok=True)
            self._open_path(log_path)
        except Exception:
            LOGGER.exception("Failed to open log folder")

    def _open_path(self, path: pathlib.Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
            LOGGER.info("Opened path: %s", path)
        except Exception:
            LOGGER.exception("Failed to open path: %s", path)

    def create_snapshot_now(self) -> Optional[pathlib.Path]:
        try:
            settings = load_settings(self.config_path)
            out_path = create_snapshot(settings)
            LOGGER.info("Created snapshot: %s", out_path)
            return out_path
        except Exception:
            LOGGER.exception("Snapshot creation failed")
            return None


def run_tray_app(config_path: pathlib.Path, log_level: str, allow_missing_com: bool = False) -> int:
    try:
        import pystray  # type: ignore
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as exc:
        LOGGER.error("Tray mode requires pystray and pillow. Install with: pip install pystray pillow")
        return 3

    controller = LoggerController(config_path=config_path, allow_missing_com=allow_missing_com)
    controller.start_logging()

    _ICON_COLORS = {
        "idle":    (74, 163, 255, 255),   # blue
        "logging": (50, 200, 50, 255),    # green
        "error":   (220, 50, 50, 255),    # red
    }

    def _make_icon(state: str) -> Any:
        color = _ICON_COLORS.get(state, _ICON_COLORS["idle"])
        image = Image.new("RGBA", (64, 64), (24, 36, 56, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), fill=color)
        draw.rectangle((30, 18, 34, 46), fill=(255, 255, 255, 255))
        return image

    _prev_state = ["idle"]

    def _update_icon() -> None:
        state = controller.state
        if state != _prev_state[0]:
            _prev_state[0] = state
            icon.icon = _make_icon(state)
            LOGGER.debug("Tray icon changed to %s", state)

    def _icon_updater() -> None:
        while not _updater_stop.is_set():
            try:
                _update_icon()
            except Exception:
                pass
            _updater_stop.wait(2)

    _updater_stop = threading.Event()

    def _toggle(_icon: Any, _item: Any) -> None:
        controller.toggle_logging()
        icon.update_menu()
        _update_icon()

    def _open_config(_icon: Any, _item: Any) -> None:
        controller.open_config_file()

    def _open_logs(_icon: Any, _item: Any) -> None:
        controller.open_log_folder()

    def _snapshot(_icon: Any, _item: Any) -> None:
        out_path = controller.create_snapshot_now()
        if out_path is not None:
            try:
                icon.notify(f"Snapshot saved: {out_path.name}", "JEOL_logger")
            except Exception:
                pass

    def _quit(icon_obj: Any, _item: Any) -> None:
        controller.stop_logging()
        _updater_stop.set()
        icon_obj.stop()

    icon = pystray.Icon(
        "JEOL_logger",
        _make_icon(controller.state),
        "JEOL_logger",
        menu=pystray.Menu(
            pystray.MenuItem(
                lambda _item: "Stop Logging" if controller.is_running else "Start Logging",
                _toggle,
                checked=lambda _item: controller.is_running,
            ),
            pystray.MenuItem("Open Config", _open_config),
            pystray.MenuItem("Open Log Folder", _open_logs),
            pystray.MenuItem("Create Lens Snapshot", _snapshot),
            pystray.MenuItem("Exit", _quit),
        ),
    )

    updater_thread = threading.Thread(target=_icon_updater, name="icon-updater", daemon=True)
    updater_thread.start()
    LOGGER.info("Starting tray app")
    icon.run()
    _updater_stop.set()
    return 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JEOL TEM COM logger")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to JSON config file (default: %APPDATA%/JEOL_logger/jeol_logger_config.json on Windows)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Poll once and exit",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log verbosity",
    )
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="Run in console mode without the tray icon",
    )
    parser.add_argument(
        "--allow-missing-com",
        action="store_true",
        help="Run without JEOL COM connection (useful for local UI/logging tests)",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    config_path = resolve_config_path(args.config)
    try:
        ensure_config_exists(config_path)
    except Exception:
        LOGGER.exception("Failed to create config file: %s", config_path)
        return 1

    if args.no_tray:
        try:
            settings = load_settings(config_path)
        except ValueError as exc:
            LOGGER.error("Invalid configuration: %s", exc)
            return 1

        LOGGER.info(
            "Configured %d parameter(s), log rotation every %.2f hour(s)",
            len(settings.metrics),
            settings.rotate_after_hours,
        )
        return run_logger(
            settings=settings,
            run_once=args.once,
            allow_missing_com=args.allow_missing_com,
        )

    if args.once:
        LOGGER.warning("--once implies console mode; disabling tray for this run")
        try:
            settings = load_settings(config_path)
        except ValueError as exc:
            LOGGER.error("Invalid configuration: %s", exc)
            return 1
        return run_logger(
            settings=settings,
            run_once=True,
            allow_missing_com=args.allow_missing_com,
        )

    return run_tray_app(
        config_path=config_path,
        log_level=args.log_level,
        allow_missing_com=args.allow_missing_com,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
