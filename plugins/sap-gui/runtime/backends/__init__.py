import platform


def select_backend():
    sysname = platform.system()
    if sysname == "Darwin":
        from .http_mac import HttpBackend
        return HttpBackend()
    if sysname == "Windows":
        from .com_win import ComBackend   # lazy: win32com only imported here
        return ComBackend()
    raise SystemExit("Unsupported OS: %s (macOS/Windows only)" % sysname)
