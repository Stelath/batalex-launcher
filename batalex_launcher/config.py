"""Configuration loading and validation for batalex-launcher.

The launcher is configured with a single YAML file. Paths may be absolute,
relative to the config file's directory, or use ``~`` and environment
variables.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
BUNDLED_CONFIG = PACKAGE_DIR.parent / "config" / "config.yaml"
USER_CONFIG_DIR = Path.home() / ".config" / "batalex-launcher"
USER_CONFIG = USER_CONFIG_DIR / "config.yaml"

DEFAULT_IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".bmp"]
DEFAULT_VIDEO_EXTS = [".mp4", ".m4v", ".mov", ".mkv", ".webm"]

VALID_ACTIONS = {"desktop", "exit", "screensaver"}


class ConfigError(Exception):
    """Raised when the configuration file is missing or invalid."""


def warn(msg: str) -> None:
    print(f"[batalex-launcher] warning: {msg}", file=sys.stderr)


def _expand(path: str, base: Path) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    if not p.is_absolute():
        p = base / p
    return p.resolve()


@dataclass
class AppItem:
    """One app tile. Either ``command`` (shell command) or ``action``
    (built-in behaviour) is set."""

    name: str
    icon: Path | None = None
    command: str | None = None
    action: str | None = None

    @property
    def is_action(self) -> bool:
        return self.action is not None


@dataclass
class AppRow:
    title: str
    items: list[AppItem]


@dataclass
class Appearance:
    background: str = "#0b0b10"
    text: str = "#f5f5f7"
    text_dim: str = "#9a9aa3"
    accent: str = "#2997ff"
    font_family: str = ""  # empty = auto-pick
    tile_width: int = 300
    tile_height: int = 170
    tile_radius: int = 26
    focus_zoom: float = 1.08
    row_label_size: int = 24
    tile_label_size: int = 19
    row_spacing: int = 30
    side_margin: int = 46


@dataclass
class HeroConfig:
    """The big picture at the top of the home screen. By default it pulls
    from the same media library as the screensaver and shuffles every
    ``cycle_seconds``."""

    enabled: bool = True
    height_ratio: float = 0.52
    cycle_seconds: float = 60.0
    show_clock: bool = True
    media_dirs: list[Path] = field(default_factory=list)  # empty = use screensaver dirs


@dataclass
class ScreensaverConfig:
    enabled: bool = True
    cycle_seconds: float = 60.0
    shuffle: bool = True
    show_clock: bool = True
    clock_24h: bool = True
    media_dirs: list[Path] = field(default_factory=list)


@dataclass
class Config:
    appearance: Appearance
    rows: list[AppRow]
    hero: HeroConfig
    screensaver: ScreensaverConfig
    image_extensions: list[str] = field(default_factory=lambda: list(DEFAULT_IMAGE_EXTS))
    video_extensions: list[str] = field(default_factory=lambda: list(DEFAULT_VIDEO_EXTS))
    idle_seconds: float = 90.0
    cursor_hide_seconds: float = 3.0
    desktop_command: str = ""
    hide_on_launch: bool = True
    restore_on_exit: bool = True
    esc_action: str = "exit"  # exit | desktop | none
    config_path: Path = BUNDLED_CONFIG

    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        cfg_path = Path(path) if path else resolve_config_path()
        if not cfg_path.is_file():
            raise ConfigError(f"Config file not found: {cfg_path}")
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {cfg_path}: {exc}") from exc
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ConfigError("Top-level config must be a mapping")

        base = cfg_path.parent
        appearance = _parse_appearance(data.get("appearance"))
        screensaver = _parse_screensaver(data.get("screensaver"), base)
        hero = _parse_hero(data.get("hero"), base, screensaver)
        rows = _parse_rows(data.get("rows"), base)
        if not rows:
            raise ConfigError("Config must define at least one row with at least one app")

        media = data.get("media", {}) or {}
        launcher = data.get("launcher", {}) or {}

        esc_action = str(launcher.get("esc_action", "exit"))
        if esc_action not in VALID_ACTIONS - {"screensaver"}:
            warn(f"launcher.esc_action '{esc_action}' invalid, using 'exit'")
            esc_action = "exit"

        return cls(
            appearance=appearance,
            rows=rows,
            hero=hero,
            screensaver=screensaver,
            image_extensions=_exts(media.get("image_extensions"), DEFAULT_IMAGE_EXTS),
            video_extensions=_exts(media.get("video_extensions"), DEFAULT_VIDEO_EXTS),
            idle_seconds=float(launcher.get("idle_seconds", 90.0)),
            cursor_hide_seconds=float(launcher.get("cursor_hide_seconds", 3.0)),
            desktop_command=str(launcher.get("desktop_command", "") or ""),
            hide_on_launch=bool(launcher.get("hide_on_launch", True)),
            restore_on_exit=bool(launcher.get("restore_on_exit", True)),
            esc_action=esc_action,
            config_path=cfg_path,
        )

    # ------------------------------------------------------------------ #
    def hero_dirs(self) -> list[Path]:
        return self.hero.media_dirs or self.screensaver.media_dirs


def resolve_config_path() -> Path:
    """Config lookup order: ~/.config/batalex-launcher/config.yaml, then a
    copy of the bundled example is created there and used."""
    if USER_CONFIG.is_file():
        return USER_CONFIG
    if BUNDLED_CONFIG.is_file():
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BUNDLED_CONFIG, USER_CONFIG)
        print(f"[batalex-launcher] created default config at {USER_CONFIG}")
        return USER_CONFIG
    raise ConfigError(
        f"No config file found. Pass one with --config "
        f"(bundled example missing at {BUNDLED_CONFIG})"
    )


def _parse_appearance(raw: object) -> Appearance:
    appearance = Appearance()
    if isinstance(raw, dict):
        for key in appearance.__dataclass_fields__:  # type: ignore[attr-defined]
            if key in raw:
                setattr(appearance, key, raw[key])
    appearance.tile_width = int(appearance.tile_width)
    appearance.tile_height = int(appearance.tile_height)
    appearance.tile_radius = int(appearance.tile_radius)
    appearance.focus_zoom = float(appearance.focus_zoom)
    appearance.row_label_size = int(appearance.row_label_size)
    appearance.tile_label_size = int(appearance.tile_label_size)
    appearance.row_spacing = int(appearance.row_spacing)
    appearance.side_margin = int(appearance.side_margin)
    return appearance


def _parse_screensaver(raw: object, base: Path) -> ScreensaverConfig:
    cfg = ScreensaverConfig()
    if isinstance(raw, dict):
        cfg.enabled = bool(raw.get("enabled", cfg.enabled))
        cfg.cycle_seconds = float(raw.get("cycle_seconds", cfg.cycle_seconds))
        cfg.shuffle = bool(raw.get("shuffle", cfg.shuffle))
        cfg.show_clock = bool(raw.get("show_clock", cfg.show_clock))
        cfg.clock_24h = bool(raw.get("clock_24h", cfg.clock_24h))
        cfg.media_dirs = [
            _expand(str(p), base) for p in raw.get("media_dirs", []) or []
        ]
    return cfg


def _parse_hero(raw: object, base: Path, screensaver: ScreensaverConfig) -> HeroConfig:
    cfg = HeroConfig()
    if isinstance(raw, dict):
        cfg.enabled = bool(raw.get("enabled", cfg.enabled))
        cfg.height_ratio = float(raw.get("height_ratio", cfg.height_ratio))
        cfg.cycle_seconds = float(raw.get("cycle_seconds", cfg.cycle_seconds))
        cfg.show_clock = bool(raw.get("show_clock", cfg.show_clock))
        cfg.media_dirs = [
            _expand(str(p), base) for p in raw.get("media_dirs", []) or []
        ]
    return cfg


def _parse_rows(raw: object, base: Path) -> list[AppRow]:
    rows: list[AppRow] = []
    if not isinstance(raw, list):
        if raw is not None:
            warn("'rows' must be a list")
        return rows
    for i, row_raw in enumerate(raw):
        if not isinstance(row_raw, dict):
            warn(f"rows[{i}] is not a mapping, skipping")
            continue
        title = str(row_raw.get("title", f"Row {i + 1}"))
        items: list[AppItem] = []
        for j, item_raw in enumerate(row_raw.get("items", []) or []):
            if not isinstance(item_raw, dict):
                warn(f"rows[{i}].items[{j}] is not a mapping, skipping")
                continue
            name = str(item_raw.get("name", "")).strip()
            if not name:
                warn(f"rows[{i}].items[{j}] has no name, skipping")
                continue
            icon_raw = item_raw.get("icon")
            icon = _expand(str(icon_raw), base) if icon_raw else None
            command = item_raw.get("command")
            action = item_raw.get("action")
            if action is not None:
                action = str(action).strip().lower()
                if action not in VALID_ACTIONS:
                    warn(f"'{name}': unknown action '{action}', skipping")
                    continue
                if action == "desktop" and command:
                    warn(f"'{name}': action tiles ignore 'command'")
            elif not command:
                warn(f"'{name}': needs 'command' or 'action', skipping")
                continue
            items.append(
                AppItem(
                    name=name,
                    icon=icon,
                    command=str(command) if command else None,
                    action=action,
                )
            )
        if items:
            rows.append(AppRow(title=title, items=items))
        else:
            warn(f"row '{title}' has no valid items, skipping")
    return rows


def _exts(raw: object, defaults: list[str]) -> list[str]:
    if not isinstance(raw, list) or not raw:
        return list(defaults)
    out = []
    for ext in raw:
        ext = str(ext).strip().lower()
        if not ext.startswith("."):
            ext = "." + ext
        out.append(ext)
    return out
