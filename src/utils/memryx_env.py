"""Utilities for configuring MemryX environment variables."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / 'config' / 'memryx_env.json'
ENV_ROOT_KEYS = ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA', 'ProgramData')
TOOL_NAMES = ('mx_nc.exe', 'mx_nc', 'mx_bench.exe', 'mx_bench')


def _default_roots() -> Tuple[Path, ...]:
    if os.name == 'nt':
        return (
            Path(r'C:/Program Files/MemryX'),
            Path(r'C:/Program Files (x86)/MemryX'),
            Path(r'C:/MemryX')
        )

    home = Path.home()
    return (
        Path('/opt/memryx'),
        Path('/opt/MemryX'),
        Path('/usr/local/memryx'),
        Path('/usr/local/MemryX'),
        home / 'memryx',
        home / 'MemryX'
    )


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding='utf-8')
    except Exception:
        pass


def _venv_bin_dir() -> Optional[Path]:
    venv = os.environ.get('VIRTUAL_ENV', '').strip()
    if not venv:
        return None
    bin_dir = Path(venv) / ('Scripts' if os.name == 'nt' else 'bin')
    if bin_dir.exists():
        return bin_dir
    return None


def _tool_exists(bin_dir: Path) -> bool:
    for tool in TOOL_NAMES:
        if (bin_dir / tool).exists():
            return True
    return False


def _find_tool_dir(root: Path) -> Optional[Path]:
    if not root.exists():
        return None
    for tool in TOOL_NAMES:
        try:
            for path in root.rglob(tool):
                if path.is_file():
                    return path.parent
        except Exception:
            continue
    return None


def _resolve_home_from_bin(bin_dir: Path) -> Path:
    if (bin_dir / 'python').exists():
        return bin_dir
    if (bin_dir.parent / 'python').exists():
        return bin_dir.parent
    return bin_dir.parent


def _detect_memryx_paths() -> Tuple[Optional[str], Optional[str]]:
    bin_env = os.environ.get('MEMRYX_BIN', '').strip()
    if bin_env and Path(bin_env).exists():
        home = _resolve_home_from_bin(Path(bin_env))
        return str(home), str(Path(bin_env))

    venv_bin = _venv_bin_dir()
    if venv_bin and _tool_exists(venv_bin):
        home = _resolve_home_from_bin(venv_bin)
        return str(home), str(venv_bin)

    tool = shutil.which('mx_nc') or shutil.which('mx_nc.exe')
    if tool:
        bin_dir = Path(tool).parent
        home = _resolve_home_from_bin(bin_dir)
        return str(home), str(bin_dir)

    for root in _candidate_roots():
        bin_dir = _find_tool_dir(root)
        if bin_dir:
            home = _resolve_home_from_bin(bin_dir)
            return str(home), str(bin_dir)
    return None, None


def _candidate_roots() -> Tuple[Path, ...]:
    roots = list(_default_roots())
    for key in ENV_ROOT_KEYS:
        value = os.environ.get(key)
        if value:
            roots.append(Path(value) / 'MemryX')
            roots.append(Path(value))

    filtered = []
    for root in roots:
        if root in filtered:
            continue
        filtered.append(root)

        parent = root.parent
        try:
            if parent.exists():
                for child in parent.iterdir():
                    if child.is_dir() and 'memryx' in child.name.lower():
                        if child not in filtered:
                            filtered.append(child)
        except Exception:
            continue

    return tuple(filtered)


def apply_memryx_env(save: bool = False) -> bool:
    existing_home = os.environ.get('MEMRYX_HOME', '').strip()
    if existing_home and Path(existing_home).exists():
        bin_dir = _find_tool_dir(Path(existing_home))
        if bin_dir:
            _prepend_path(str(bin_dir))
        return True

    bin_env = os.environ.get('MEMRYX_BIN', '').strip()
    if bin_env and Path(bin_env).exists():
        bin_path = Path(bin_env)
        _prepend_path(str(bin_path))
        if not os.environ.get('MEMRYX_HOME'):
            os.environ['MEMRYX_HOME'] = str(_resolve_home_from_bin(bin_path))
        if save:
            _save_config({'MEMRYX_HOME': os.environ.get('MEMRYX_HOME', ''), 'MEMRYX_BIN': bin_env})
        return True

    venv_bin = _venv_bin_dir()
    if venv_bin and _tool_exists(venv_bin):
        _prepend_path(str(venv_bin))
        if not os.environ.get('MEMRYX_HOME'):
            os.environ['MEMRYX_HOME'] = str(_resolve_home_from_bin(venv_bin))
        if save:
            _save_config({'MEMRYX_HOME': os.environ.get('MEMRYX_HOME', ''), 'MEMRYX_BIN': str(venv_bin)})
        return True

    config = _load_config()
    config_home = (config.get('MEMRYX_HOME') or '').strip()
    config_bin = (config.get('MEMRYX_BIN') or '').strip()

    if config_home and Path(config_home).exists():
        os.environ['MEMRYX_HOME'] = config_home
        if config_bin and Path(config_bin).exists():
            _prepend_path(config_bin)
        else:
            bin_dir = _find_tool_dir(Path(config_home))
            if bin_dir:
                _prepend_path(str(bin_dir))
                config_bin = str(bin_dir)
        if save:
            _save_config({'MEMRYX_HOME': config_home, 'MEMRYX_BIN': config_bin})
        return True

    home, bin_dir = _detect_memryx_paths()
    if not home:
        return False

    os.environ['MEMRYX_HOME'] = home
    if bin_dir:
        _prepend_path(bin_dir)

    if save:
        _save_config({'MEMRYX_HOME': home, 'MEMRYX_BIN': bin_dir or ''})
    return True


def _prepend_path(path_value: str) -> None:
    current = os.environ.get('PATH', '')
    parts = [p for p in current.split(os.pathsep) if p]
    if path_value in parts:
        return
    os.environ['PATH'] = os.pathsep.join([path_value] + parts)
