from __future__ import annotations

import threading
from typing import Dict, Optional

try:
    import essentia
    import essentia.standard as es
except ImportError:
    es = None                

_mono_loaders: Dict[int, "es.MonoLoader"] = {}
_lock = threading.Lock()

def load_mono(filename: str, sample_rate: int = 16000):
    """Reuse a single MonoLoader instance per sample_rate and reconfigure it.

    This avoids recreating Essentia algorithm networks on every call and
    silences the repetitive "No network created" warnings.
    """
    if es is None:
        raise RuntimeError("Essentia is not available in this environment.")
    with _lock:
        loader = _mono_loaders.get(sample_rate)
        if loader is None:
            loader = es.MonoLoader(sampleRate=sample_rate)
            _mono_loaders[sample_rate] = loader
        loader.configure(filename=filename, sampleRate=sample_rate)
        return loader()

