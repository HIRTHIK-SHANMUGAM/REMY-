"""
Shell tool — terminal command execution behind the permission engine.

Hard denylist (rm -rf, disk formatting, fork bombs, sudo, pipe-to-shell…)
is enforced in code by remy.permissions.engine.check_shell_command and can
NOT be overridden by approval. Read-only commands run in the LOGGED tier;
anything else blocks for explicit user approval.
"""

import subprocess

from remy.config import config


def register(mcp, guard):

    @mcp.tool()
    def run_shell(command: str, timeout_s: int = 30) -> str:
        """
        Run a terminal command in the workspace directory. Read-only commands
        run immediately (logged); state-changing commands require user
        approval; destructive patterns are refused outright.
        """
        def impl(command: str, timeout_s: int = 30) -> str:
            timeout_s = min(max(1, timeout_s), 120)
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(config.ALLOWED_DIRS[0]),
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
            except subprocess.TimeoutExpired:
                return f"Command timed out after {timeout_s}s."
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            parts = [f"exit code: {proc.returncode}"]
            if out:
                parts.append(f"stdout:\n{out[:8000]}")
            if err:
                parts.append(f"stderr:\n{err[:2000]}")
            return "\n".join(parts)
        return guard(impl, "run_shell")(command, timeout_s)
