"""
Screen perception — screenshots + optional vision-model description, so REMY
can "see" the screen when asked or while monitoring. Read-only (AUTO tier);
captures are saved into the workspace, never transmitted anywhere unless the
description step explicitly calls the configured LLM.
"""

from datetime import datetime

from remy.config import config


def _capture(path) -> str:
    """Save a full-screen capture to `path` using mss (preferred) or pyautogui."""
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            mss.tools.to_png(shot.rgb, shot.size, output=str(path))
        return str(path)
    except Exception:
        pass
    try:
        import pyautogui
        pyautogui.screenshot(str(path))
        return str(path)
    except Exception as exc:
        raise RuntimeError(
            f"Screen capture unavailable ({exc}). "
            'Install desktop extras: pip install "remy[desktop]"') from exc


def register(mcp, guard):

    @mcp.tool()
    def capture_screen() -> str:
        """Take a screenshot; returns the saved PNG path inside the workspace."""
        def impl() -> str:
            shots_dir = config.ALLOWED_DIRS[0] / "screenshots"
            shots_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            return f"Screenshot saved: {_capture(shots_dir / f'screen-{stamp}.png')}"
        return guard(impl, "capture_screen")()

    @mcp.tool()
    def describe_screen() -> str:
        """
        Screenshot the display and describe what's visible — vision model when
        configured, local OCR (pytesseract) as an offline fallback.
        """
        def impl() -> str:
            shots_dir = config.ALLOWED_DIRS[0] / "screenshots"
            shots_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path = _capture(shots_dir / f"screen-{stamp}.png")
            try:
                from remy.agents.base import describe_image
                description = describe_image(path)
            except Exception as exc:
                description = _local_ocr(path, str(exc))
            return f"Screenshot: {path}\n\n{description}"
        return guard(impl, "describe_screen")()


def _local_ocr(path: str, vision_error: str) -> str:
    """Offline fallback: extract visible text with pytesseract if present."""
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(path)).strip()
        if text:
            return ("(vision model unavailable — local OCR text follows)\n"
                    + text[:4000])
        return "(vision model unavailable; local OCR found no readable text)"
    except Exception:
        return (f"(vision model unavailable: {vision_error}; install "
                'pytesseract + tesseract for offline OCR: '
                'pip install "remy[desktop]")')
