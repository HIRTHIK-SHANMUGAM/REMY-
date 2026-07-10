"""
Application control — open/close/list apps, cross-platform.

macOS: `open -a` / osascript.  Windows: `start` / taskkill.  Linux: direct exec.
Opening an app is LOGGED tier; closing one requires approval (unsaved work).
"""

import platform
import shlex
import subprocess

SYSTEM = platform.system()


def register(mcp, guard):

    @mcp.tool()
    def open_app(name: str) -> str:
        """Open (or focus) an application by name, e.g. 'Safari', 'notepad'."""
        def impl(name: str) -> str:
            try:
                if SYSTEM == "Darwin":
                    subprocess.run(["open", "-a", name], check=True, timeout=10)
                elif SYSTEM == "Windows":
                    subprocess.run(f'start "" "{name}"', shell=True, check=True, timeout=10)
                else:
                    subprocess.Popen(shlex.split(name),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"Opened {name}."
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                    FileNotFoundError) as exc:
                return f"Could not open {name}: {exc}"
        return guard(impl, "open_app")(name)

    @mcp.tool()
    def close_app(name: str) -> str:
        """Close an application by name. Requires user approval (may lose unsaved work)."""
        def impl(name: str) -> str:
            try:
                if SYSTEM == "Darwin":
                    subprocess.run(
                        ["osascript", "-e", f'tell application "{name}" to quit'],
                        check=True, timeout=10)
                elif SYSTEM == "Windows":
                    subprocess.run(["taskkill", "/IM", f"{name}.exe"],
                                   check=True, timeout=10)
                else:
                    subprocess.run(["pkill", "-f", name], timeout=10)
                return f"Closed {name}."
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                return f"Could not close {name}: {exc}"
        return guard(impl, "close_app")(name)

    @mcp.tool()
    def list_open_apps() -> str:
        """List currently running user-visible applications."""
        def impl() -> str:
            try:
                if SYSTEM == "Darwin":
                    out = subprocess.run(
                        ["osascript", "-e",
                         'tell application "System Events" to get name of every process whose background only is false'],
                        capture_output=True, text=True, timeout=10).stdout
                    return out.strip() or "No apps reported."
                if SYSTEM == "Windows":
                    out = subprocess.run(
                        ["tasklist", "/FI", "STATUS eq RUNNING"],
                        capture_output=True, text=True, timeout=10).stdout
                    return out[:4000]
                out = subprocess.run(["ps", "-eo", "comm", "--no-headers"],
                                     capture_output=True, text=True, timeout=10).stdout
                names = sorted(set(out.split()))
                return ", ".join(names[:80])
            except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                return f"Could not list apps: {exc}"
        return guard(impl, "list_open_apps")()
