"""Cross-platform 'copy text to clipboard' helper.

Order of preference:
1. pyperclip if installed (handles macOS / Linux / Windows uniformly)
2. macOS ``pbcopy`` subprocess
3. Linux ``xclip`` or ``wl-copy`` subprocess
Returns True on success, False otherwise (caller can notify the user)."""
from __future__ import annotations

import platform
import shutil
import subprocess


def copy_to_clipboard(text: str) -> bool:
    # 1. pyperclip
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return True
    except Exception:
        pass
    # 2. macOS pbcopy
    if platform.system() == "Darwin":
        try:
            p = subprocess.run(["pbcopy"], input=text, text=True,
                               check=True, timeout=2)
            return p.returncode == 0
        except Exception:
            return False
    # 3. Linux X11 / Wayland
    for tool, args in (("xclip", ["-selection", "clipboard"]),
                       ("wl-copy", [])):
        if shutil.which(tool):
            try:
                subprocess.run([tool, *args], input=text, text=True,
                               check=True, timeout=2)
                return True
            except Exception:
                return False
    return False
