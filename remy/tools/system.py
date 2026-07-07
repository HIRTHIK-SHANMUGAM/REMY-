"""
System tools — time, environment info, and health metrics (used by standing
orders: disk space, CPU).
"""

import datetime
import platform
import shutil


def get_health_snapshot() -> dict:
    """Raw health metrics — also called directly by the heartbeat/Watcher."""
    snapshot: dict = {}
    usage = shutil.disk_usage("/")
    snapshot["disk_free_percent"] = round(usage.free / usage.total * 100, 1)
    try:
        import psutil
        snapshot["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        snapshot["memory_percent"] = psutil.virtual_memory().percent
        snapshot["boot_time"] = datetime.datetime.fromtimestamp(
            psutil.boot_time()).isoformat()
    except ImportError:
        snapshot["cpu_percent"] = None
        snapshot["memory_percent"] = None
    return snapshot


def register(mcp, guard):

    @mcp.tool()
    def get_current_time() -> str:
        """Return the current date and time in ISO 8601 format."""
        def impl() -> str:
            return datetime.datetime.now().isoformat()
        return guard(impl, "get_current_time")()

    @mcp.tool()
    def get_system_info() -> dict:
        """Return basic information about the host system."""
        def impl() -> dict:
            return {
                "os": platform.system(),
                "os_version": platform.version(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
            }
        return guard(impl, "get_system_info")()

    @mcp.tool()
    def get_system_health() -> dict:
        """Return disk, CPU, and memory health metrics."""
        def impl() -> dict:
            return get_health_snapshot()
        return guard(impl, "get_system_health")()
