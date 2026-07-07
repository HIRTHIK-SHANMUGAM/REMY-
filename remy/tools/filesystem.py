"""
Filesystem tools — scoped to the allowlisted workspace directories.

The permission engine escalates any path outside config.ALLOWED_DIRS to the
approval tier, and delete/move always require approval regardless of path.
"""

import shutil
from pathlib import Path

from remy.config import config


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def register(mcp, guard):

    @mcp.tool()
    def read_file(path: str, max_chars: int = 20000) -> str:
        """Read a text file. Paths outside the workspace require user approval."""
        def impl(path: str, max_chars: int = 20000) -> str:
            p = _resolve(path)
            if not p.is_file():
                return f"Not a file: {p}"
            text = p.read_text(encoding="utf-8", errors="replace")
            if len(text) > max_chars:
                return text[:max_chars] + f"\n…(truncated, {len(text)} chars total)"
            return text
        return guard(impl, "read_file")(path, max_chars)

    @mcp.tool()
    def list_directory(path: str = "") -> str:
        """List a directory (defaults to the primary workspace)."""
        def impl(path: str = "") -> str:
            p = _resolve(path) if path else config.ALLOWED_DIRS[0]
            if not p.is_dir():
                return f"Not a directory: {p}"
            rows = []
            for child in sorted(p.iterdir()):
                kind = "dir " if child.is_dir() else "file"
                size = child.stat().st_size if child.is_file() else ""
                rows.append(f"{kind}  {child.name}  {size}")
            return f"{p}:\n" + ("\n".join(rows) if rows else "(empty)")
        return guard(impl, "list_directory")(path)

    @mcp.tool()
    def search_files(pattern: str, path: str = "") -> str:
        """Glob-search for files (e.g. '**/*.md') under a workspace directory."""
        def impl(pattern: str, path: str = "") -> str:
            p = _resolve(path) if path else config.ALLOWED_DIRS[0]
            matches = [str(m) for m in list(p.glob(pattern))[:100]]
            return "\n".join(matches) if matches else "No matches."
        return guard(impl, "search_files")(pattern, path)

    @mcp.tool()
    def write_file(path: str, content: str) -> str:
        """Write (create/overwrite) a text file inside the workspace."""
        def impl(path: str, content: str) -> str:
            p = _resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} chars to {p}"
        return guard(impl, "write_file")(path, content)

    @mcp.tool()
    def append_file(path: str, content: str) -> str:
        """Append text to a file inside the workspace."""
        def impl(path: str, content: str) -> str:
            p = _resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(content)
            return f"Appended {len(content)} chars to {p}"
        return guard(impl, "append_file")(path, content)

    @mcp.tool()
    def create_directory(path: str) -> str:
        """Create a directory (and parents) inside the workspace."""
        def impl(path: str) -> str:
            p = _resolve(path)
            p.mkdir(parents=True, exist_ok=True)
            return f"Created {p}"
        return guard(impl, "create_directory")(path)

    @mcp.tool()
    def delete_file(path: str) -> str:
        """Delete a file or empty directory. ALWAYS requires user approval."""
        def impl(path: str) -> str:
            p = _resolve(path)
            if p.is_dir():
                p.rmdir()  # only empty dirs — recursive delete is never offered
                return f"Removed empty directory {p}"
            p.unlink()
            return f"Deleted {p}"
        return guard(impl, "delete_file")(path)

    @mcp.tool()
    def move_file(source: str, destination: str) -> str:
        """Move/rename a file. ALWAYS requires user approval."""
        def impl(source: str, destination: str) -> str:
            src, dst = _resolve(source), _resolve(destination)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"Moved {src} → {dst}"
        return guard(impl, "move_file")(source, destination)
