"""Memory: how much the process holds in RAM and on the GPU (for the report's "memory" entry), and giving back what is
no longer used (the PyTorch cache on the GPU, the freed heap to the system).

torch is never imported here: the GPU numbers are read only when another module already imported it, so measuring a
stage that runs before the model (the request check) costs nothing. The rest is pure.
"""
import gc
import os
import sys

MB = 1024 * 1024


def parse_status(text):
    """The resident memory (VmRSS) of a /proc/<pid>/status text, in MB; None without the line."""
    for line in text.splitlines():
        if line.startswith("VmRSS:"):
            return round(int(line.split()[1]) / 1024)
    return None


def _linux_ram():
    try:
        with open("/proc/self/status", encoding="ascii", errors="replace") as f:
            return parse_status(f.read())
    except OSError:
        return None


def _windows_ram():
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + \
                [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not kernel.K32GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return None
        return round(counters.WorkingSetSize / MB)
    except Exception:  # only a measurement: never a reason for a generation to fail
        return None


def ram_mb():
    """The RAM the process holds now, in MB (Linux and Windows); None where it cannot be read."""
    if sys.platform.startswith("linux"):
        return _linux_ram()
    if os.name == "nt":
        return _windows_ram()
    return None


def _cuda():
    """torch.cuda when torch was already imported and there is a GPU; None otherwise (nothing is imported here)."""
    torch = sys.modules.get("torch")
    if torch is None or not torch.cuda.is_available():
        return None
    return torch.cuda


def entry(vram_peak, vram_reserved, ram):
    """A stage's memory entry: the GPU peak allocated during the stage and what PyTorch keeps reserved at its end (in
    bytes, given as MB), and the process RAM (already in MB). None where it was not measured."""
    as_mb = (lambda b: None if b is None else round(b / MB))
    return {"vram_peak_mb": as_mb(vram_peak), "vram_reserved_mb": as_mb(vram_reserved), "ram_mb": ram}


def start():
    """Starts measuring a stage: resets the GPU peak."""
    cuda = _cuda()
    if cuda:
        cuda.reset_peak_memory_stats()


def measure():
    """The memory entry of the stage that just ran (see entry)."""
    cuda = _cuda()
    return entry(cuda.max_memory_allocated() if cuda else None, cuda.memory_reserved() if cuda else None, ram_mb())


def trim():
    """Gives the heap Python freed back to the system (glibc's malloc_trim; Linux only, nothing elsewhere)."""
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):  # not glibc (musl, ...)
        pass


def free():
    """Gives back what is no longer used: the Python objects in cycles, the GPU memory PyTorch keeps in its cache, and
    the freed heap."""
    gc.collect()
    cuda = _cuda()
    if cuda:
        cuda.empty_cache()
    trim()
