#!/usr/bin/env python3
"""
Oxidus Launcher
Simple executable script to launch the Oxidus consciousness system
"""

import sys
import os
import getpass
import threading
import subprocess
import traceback
import webbrowser
import time
import socket
import shlex
import shutil
from pathlib import Path
from typing import Optional

from src.utils.memryx_env import apply_memryx_env

# Ensure we're in the right directory
project_root = Path(__file__).parent

# Add src to path
sys.path.insert(0, str(project_root / 'src'))

# Change to project directory
os.chdir(project_root)

TOKEN_FILE = project_root / 'config' / 'admin_token.txt'
DEFAULT_ADMIN_TOKEN = 'Jckdr2024!!'
LAUNCH_LOG = project_root / 'logs' / 'launch_oxidus.log'
NPM_HARDWIRED = Path(r'C:/Program Files/nodejs/npm.cmd')


def _python_exe() -> Path:
    venv_python = project_root / '.venv' / 'Scripts' / 'python.exe'
    return venv_python if venv_python.exists() else Path(sys.executable)


def _is_windows() -> bool:
    return os.name == 'nt'


def _env_truthy(name: str, default: str = '0') -> bool:
    return os.environ.get(name, default).lower() in {'1', 'true', 'yes', 'on'}


def _log_launch(message: str) -> None:
    try:
        LAUNCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with LAUNCH_LOG.open('a', encoding='utf-8') as log:
            log.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _show_error(message: str) -> None:
    _log_launch(f"ERROR: {message}")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('Oxidus Launch Error', message)
        root.destroy()
    except Exception:
        print(message)


def _prompt_admin_token() -> str:
    if sys.stdin and sys.stdin.isatty():
        return getpass.getpass('Admin token: ').strip()
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        token = simpledialog.askstring('Oxidus Admin Token', 'Enter admin token:', show='*')
        root.destroy()
        return (token or '').strip()
    except Exception:
        return ''


def _load_saved_token() -> str:
    try:
        if TOKEN_FILE.exists():
            return TOKEN_FILE.read_text(encoding='utf-8').strip()
    except Exception:
        pass
    return ''


def _ensure_default_token() -> None:
    if os.environ.get('OXIDUS_ADMIN_TOKEN'):
        return
    saved = _load_saved_token()
    token = saved or DEFAULT_ADMIN_TOKEN
    os.environ['OXIDUS_ADMIN_TOKEN'] = token
    if not saved:
        _save_token(token)


def _save_token(token: str) -> None:
    try:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token.strip(), encoding='utf-8')
    except Exception:
        pass


def _confirm_save_token() -> bool:
    if sys.stdin and sys.stdin.isatty():
        answer = input('Save admin token for future launches? [y/N]: ').strip().lower()
        return answer in {'y', 'yes'}
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        should_save = messagebox.askyesno('Save Admin Token', 'Save admin token for future launches?')
        root.destroy()
        return should_save
    except Exception:
        return False


def _relaunch_with_venv() -> None:
    venv_python = project_root / '.venv' / 'Scripts' / 'python.exe'
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        _log_launch(f"Relaunching with venv: {venv_python}")
        subprocess.Popen([str(venv_python), str(Path(__file__).resolve())], env=os.environ.copy())
        sys.exit(0)


def _wsl_available() -> bool:
    if not _is_windows():
        return False
    try:
        result = subprocess.run(
            ['wsl', '-e', 'bash', '-lc', 'true'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _warm_wsl() -> None:
    if not _is_windows():
        return
    if os.environ.get('OXIDUS_WSL_MX', '1').lower() in {'0', 'false', 'off', 'no'}:
        return
    try:
        _log_launch('Warming WSL for MemryX')
        subprocess.run(
            ['wsl', '-e', 'bash', '-lc', 'echo "WSL ready"'],
            capture_output=True,
            text=True,
            timeout=10
        )
    except Exception as exc:
        _log_launch(f'WSL warm-up failed: {exc}')


def _wsl_path(win_path: Path) -> str:
    result = subprocess.run(
        ['wsl', 'wslpath', '-a', str(win_path)],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or 'wslpath failed')
    return result.stdout.strip()


def _wsl_python() -> str:
    probe = (
        'if [ -x "$HOME/mx/bin/python" ]; then echo "$HOME/mx/bin/python"; '
        'elif command -v python3 >/dev/null 2>&1; then command -v python3; '
        'else exit 1; fi'
    )
    result = subprocess.run(
        ['wsl', '-e', 'bash', '-lc', probe],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode != 0:
        raise RuntimeError('No python3 in WSL')
    return result.stdout.strip()


def _should_use_wsl() -> bool:
    if not _is_windows():
        return False
    if _env_truthy('OXIDUS_WSL', '0'):
        _log_launch('WSL forced by OXIDUS_WSL=1')
        return True
    if (project_root / '.venv' / 'Scripts' / 'python.exe').exists():
        return False
    available = _wsl_available()
    if available:
        _log_launch('WSL available and no local venv found, using WSL')
    return available


def _maybe_open_browser() -> None:
    if os.environ.get('OXIDUS_OPEN_BROWSER', '1').lower() in {'0', 'false', 'off', 'no'}:
        return
    try:
        time.sleep(2)
        webbrowser.open('http://127.0.0.1:5000')
    except Exception:
        pass


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int, timeout_s: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        if _port_open(host, port):
            return True
        time.sleep(0.5)
    return False


def _launch_flask_wsl() -> None:
    if _port_open('127.0.0.1', 5000):
        _maybe_open_browser()
        return

    try:
        wsl_project = _wsl_path(project_root)
        wsl_python = _wsl_python()
    except Exception as exc:
        _show_error(f'WSL launch failed: {exc}')
        return

    log_path = project_root / 'logs' / 'web_gui_startup_wsl.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)

    activate = 'source "$HOME/mx/bin/activate" >/dev/null 2>&1 || true'
    cmd = (
        f'cd {shlex.quote(wsl_project)} && {activate} && '
        f'exec {shlex.quote(wsl_python)} web_gui.py'
    )

    _log_launch(f"Launching Flask in WSL: {wsl_python} @ {wsl_project}")
    with log_path.open('a', encoding='utf-8') as log:
        subprocess.Popen(
            ['wsl', '-e', 'bash', '-lc', cmd],
            stdout=log,
            stderr=log
        )

    if _wait_for_port('127.0.0.1', 5000, timeout_s=30.0):
        _maybe_open_browser()
    else:
        _show_error('Oxidus failed to start in WSL. Check logs/web_gui_startup_wsl.log')


def _launch_flask_only(open_browser: bool = True) -> None:
    if _should_use_wsl():
        _launch_flask_wsl()
        return
    if _port_open('127.0.0.1', 5000):
        if open_browser:
            _maybe_open_browser()
        return

    python_exe = _python_exe()
    _log_launch(f"Launching Flask locally: {python_exe}")
    log_path = project_root / 'logs' / 'web_gui_startup.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as log:
        subprocess.Popen(
            [str(python_exe), 'web_gui.py'],
            env=os.environ.copy(),
            cwd=str(project_root),
            stdout=log,
            stderr=log
        )

    if _wait_for_port('127.0.0.1', 5000, timeout_s=20.0):
        if open_browser:
            _maybe_open_browser()
    else:
        _show_error('Oxidus failed to start web server. Check logs/web_gui_startup.log')


def _electron_dir() -> Path:
    return project_root / 'electron'


def _electron_installed() -> bool:
    if not _electron_dir().exists():
        return False
    if not (_electron_dir() / 'package.json').exists():
        return False
    return True


def _npm_available() -> bool:
    return _npm_command() is not None


def _npm_command() -> Optional[list]:
    if _is_windows() and NPM_HARDWIRED.exists():
        return [str(NPM_HARDWIRED)]
    npm = shutil.which('npm')
    if npm:
        return [npm]
    return None


def _electron_bin() -> Optional[Path]:
    base = _electron_dir() / 'node_modules' / '.bin'
    if _is_windows():
        candidate = base / 'electron.cmd'
    else:
        candidate = base / 'electron'
    return candidate if candidate.exists() else None


def _ensure_electron_deps() -> bool:
    if _electron_bin() is not None:
        return True
    npm_cmd = _npm_command()
    if not npm_cmd:
        _log_launch('npm not available for Electron install')
        _show_error('Electron dependencies missing and npm is not available. Install Node.js + npm.')
        return False

    log_path = project_root / 'logs' / 'electron_install.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _log_launch('Installing Electron dependencies via npm install')
    with log_path.open('a', encoding='utf-8') as log:
        result = subprocess.run(
            npm_cmd + ['install'],
            cwd=str(_electron_dir()),
            env=os.environ.copy(),
            stdout=log,
            stderr=log
        )
    if result.returncode != 0:
        _show_error('Electron install failed. Check logs/electron_install.log')
        return False
    return _electron_bin() is not None


def _launch_electron() -> bool:
    if not _electron_installed():
        _log_launch('Electron app not installed (missing electron/package.json)')
        return False
    if not _ensure_electron_deps():
        _log_launch('Electron dependencies not available')
        return False

    _launch_flask_only(open_browser=False)

    log_path = project_root / 'logs' / 'electron_startup.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault('OXIDUS_BASE_URL', 'http://127.0.0.1:5000')
    env.setdefault('ELECTRON_ENABLE_LOGGING', '1')
    env.setdefault('ELECTRON_ENABLE_STACK_DUMPING', '1')

    npm_cmd = _npm_command()
    if not npm_cmd:
        _log_launch('npm not available for Electron start')
        _show_error('Electron start failed: npm not available.')
        return False

    _log_launch('Starting Electron via npm start')
    with log_path.open('a', encoding='utf-8') as log:
        subprocess.Popen(
            npm_cmd + ['start'],
            cwd=str(_electron_dir()),
            env=env,
            stdout=log,
            stderr=log
        )
    return True


def _launch_memryx_monitor() -> None:
    if os.environ.get('OXIDUS_MEMRYX_MONITOR', '1').lower() in {'0', 'false', 'off', 'no'}:
        return
    script_path = project_root / 'scripts' / 'memryx_monitor.py'
    if not script_path.exists():
        return

    interval = os.environ.get('OXIDUS_MEMRYX_MONITOR_INTERVAL', '15')
    python_exe = _python_exe()

    try:
        creationflags = subprocess.CREATE_NEW_CONSOLE
    except AttributeError:
        creationflags = 0

    cmd = [
        str(python_exe),
        str(script_path),
        '--interval',
        str(interval)
    ]
    subprocess.Popen(
        cmd,
        env=os.environ.copy(),
        cwd=str(project_root),
        creationflags=creationflags
    )


# Launch the GUI
if __name__ == '__main__':
    _log_launch(f"Launcher started with python: {sys.executable}")
    _relaunch_with_venv()
    apply_memryx_env(save=True)
    _ensure_default_token()

    os.environ.setdefault('OXIDUS_WSL_MX', '1')
    os.environ.setdefault('OXIDUS_WSL_MX_VENV', '$HOME/mx')
    os.environ.setdefault('OXIDUS_MOLTBOOK_ENABLED', '1')
    os.environ.setdefault('OXIDUS_MOLTBOOK_INTERVAL_MIN', '30')
    os.environ.setdefault('OXIDUS_MOLTBOOK_LIMIT', '10')
    os.environ.setdefault('OXIDUS_MOLTBOOK_FILTER', 'u/grok-1')
    _warm_wsl()

    _launch_memryx_monitor()

    print("Starting Oxidus...")
    print("=" * 60)

    use_electron = os.environ.get('OXIDUS_USE_ELECTRON', '1').lower() in {'1', 'true', 'yes', 'on'}
    if use_electron and _launch_electron():
        sys.exit(0)

    use_qt = os.environ.get('OXIDUS_USE_QT', '0').lower() in {'1', 'true', 'yes', 'on'}
    if not use_qt:
        _launch_flask_only()
        sys.exit(0)

    try:
        from chromium_gui import OxidusChromiumGUI, QApplication

        # Create Qt application
        app = QApplication(sys.argv)

        # Create and show main window
        window = OxidusChromiumGUI()
        window.show()

        print("Oxidus GUI launched successfully!")
        print("Navigate to: http://127.0.0.1:5000")
        print("=" * 60)
        print("Press CTRL+C to stop")

        sys.exit(app.exec_())

    except ImportError as e:
        message = (
            f"Error: Missing dependency - {e}\n\n"
            "Make sure you have installed requirements:\n"
            "  pip install -r requirements.txt"
        )
        _show_error(message)
        _launch_flask_only()
        sys.exit(0)
    except Exception as e:
        message = f"Error launching Oxidus: {e}\n\n{traceback.format_exc()}"
        _show_error(message)
        _launch_flask_only()
        sys.exit(0)
