"""
Input automation — mouse/keyboard control via pyautogui.

Highest-risk tool category. Every action here is REQUIRES_APPROVAL tier:
the user confirms each individual call before anything moves or types.
Degrades gracefully to a clear error if pyautogui isn't installed
(install with: pip install "remy[desktop]").
"""


def _pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = True  # slam cursor into a corner to abort
        return pyautogui
    except Exception as exc:  # ImportError or headless-display errors
        raise RuntimeError(
            f"Input automation unavailable ({exc}). "
            'Install desktop extras: pip install "remy[desktop]"') from exc


def register(mcp, guard):

    @mcp.tool()
    def type_text(text: str, interval_s: float = 0.02) -> str:
        """Type text at the current cursor position. Requires per-action approval."""
        def impl(text: str, interval_s: float = 0.02) -> str:
            gui = _pyautogui()
            gui.typewrite(text, interval=max(0.0, min(interval_s, 0.5)))
            return f"Typed {len(text)} characters."
        return guard(impl, "type_text")(text, interval_s)

    @mcp.tool()
    def press_keys(keys: str) -> str:
        """Press a key combo, e.g. 'ctrl+s' or 'command+space'. Requires approval."""
        def impl(keys: str) -> str:
            gui = _pyautogui()
            parts = [k.strip().lower() for k in keys.split("+") if k.strip()]
            if not parts:
                return "No keys given."
            gui.hotkey(*parts)
            return f"Pressed {'+'.join(parts)}."
        return guard(impl, "press_keys")(keys)

    @mcp.tool()
    def click_mouse(x: int, y: int, button: str = "left", double: bool = False) -> str:
        """Click at screen coordinates. Requires per-action approval."""
        def impl(x: int, y: int, button: str = "left", double: bool = False) -> str:
            gui = _pyautogui()
            if double:
                gui.doubleClick(x, y, button=button)
            else:
                gui.click(x, y, button=button)
            return f"{'Double-c' if double else 'C'}licked {button} at ({x}, {y})."
        return guard(impl, "click_mouse")(x, y, button, double)

    @mcp.tool()
    def move_mouse(x: int, y: int, duration_s: float = 0.2) -> str:
        """Move the mouse cursor to screen coordinates. Requires approval."""
        def impl(x: int, y: int, duration_s: float = 0.2) -> str:
            gui = _pyautogui()
            gui.moveTo(x, y, duration=max(0.0, min(duration_s, 2.0)))
            return f"Moved cursor to ({x}, {y})."
        return guard(impl, "move_mouse")(x, y, duration_s)
