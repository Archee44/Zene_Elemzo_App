import sys
import io
from contextlib import contextmanager

class _StreamFilter(io.TextIOBase):
    def __init__(self, real_stream, patterns):
        self._real = real_stream
        self._patterns = patterns or []

    def write(self, s):
        try:
            text = str(s)
        except Exception:
            text = s
        for line in text.splitlines(True):
            if any(p in line for p in self._patterns):
                continue
            try:
                self._real.write(line)
            except Exception:
                pass
        return len(s)

    def flush(self):
        try:
            self._real.flush()
        except Exception:
            pass

@contextmanager
def suppress_warnings(patterns=None, also_stdout=False):
    """Temporarily suppress lines that match any pattern from stderr (and stdout optionally).

    Default patterns filter Essentia's repetitive warning lines.
    """
    if patterns is None:
        patterns = [
            "[ WARNING",                             
            "No network created",                             
        ]
    old_err = sys.stderr
    old_out = sys.stdout
    try:
        sys.stderr = _StreamFilter(old_err, patterns)
        if also_stdout:
            sys.stdout = _StreamFilter(old_out, patterns)
        yield
    finally:
        sys.stderr = old_err
        if also_stdout:
            sys.stdout = old_out

def run_quietly(fn, *args, **kwargs):
    """Run callable while suppressing common Essentia warning lines."""
    with suppress_warnings():
        return fn(*args, **kwargs)

def install_global_warning_filter(patterns=None, also_stdout=True):
    """Install a process-wide stream filter that drops lines matching patterns.

    Use at app startup to silence noisy C++ WARNING lines that bypass Python
    logging (e.g., Essentia/TensorFlow native prints).
    """
    if patterns is None:
        patterns = [
            "[ WARNING",                                     
            "No network created",                                        
        ]
    sys.stderr = _StreamFilter(sys.stderr, patterns)
    if also_stdout:
        sys.stdout = _StreamFilter(sys.stdout, patterns)
