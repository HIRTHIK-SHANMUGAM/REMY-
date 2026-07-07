"""Isolate all REMY runtime state into a temp dir before any remy import."""

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="remy-test-")
os.environ["REMY_DATA_DIR"] = _tmp
os.environ["REMY_ALLOWED_DIRS"] = os.path.join(_tmp, "workspace")
os.environ["REMY_HEARTBEAT_MINUTES"] = "0"
os.environ.pop("ANTHROPIC_API_KEY", None)
