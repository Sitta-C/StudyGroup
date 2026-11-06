"""Register the bundled OFL font for this process, without installing fonts."""

import ctypes
import ctypes.util
from functools import lru_cache
from pathlib import Path
import sys

FONT_FILE = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSansThai.ttf"


@lru_cache(maxsize=1)
def load_bundled_font():
    if not FONT_FILE.is_file():
        return False
    try:
        if sys.platform == "darwin":
            cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            ct = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
            cf.CFURLCreateFromFileSystemRepresentation.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool)
            cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
            cf.CFRelease.argtypes = (ctypes.c_void_p,)
            cf.CFRelease.restype = None
            ct.CTFontManagerRegisterFontsForURL.argtypes = (ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p))
            ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
            path = bytes(FONT_FILE)
            url = cf.CFURLCreateFromFileSystemRepresentation(None, path, len(path), False)
            if not url:
                return False
            error = ctypes.c_void_p()
            try:
                # kCTFontManagerScopeProcess = 1: private, removed on process exit.
                return bool(ct.CTFontManagerRegisterFontsForURL(url, 1, ctypes.byref(error)))
            finally:
                cf.CFRelease(url)
                if error.value:
                    cf.CFRelease(error)
        if sys.platform == "win32":
            add = ctypes.windll.gdi32.AddFontResourceExW
            add.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p)
            add.restype = ctypes.c_int
            return bool(add(str(FONT_FILE), 0x10, None))  # FR_PRIVATE
        library = ctypes.util.find_library("fontconfig")
        if library:
            fc = ctypes.CDLL(library)
            fc.FcConfigGetCurrent.restype = ctypes.c_void_p
            fc.FcConfigAppFontAddFile.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
            fc.FcConfigAppFontAddFile.restype = ctypes.c_int
            return bool(fc.FcConfigAppFontAddFile(fc.FcConfigGetCurrent(), bytes(FONT_FILE)))
    except (OSError, AttributeError):
        pass
    return False
