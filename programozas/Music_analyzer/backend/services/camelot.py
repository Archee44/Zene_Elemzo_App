import numpy as np

try:
    import essentia
    import essentia.standard as es
except ImportError:
    essentia = None
    es = None

Camelot_map = {
    "C:maj": "8B", "G:maj": "9B", "D:maj": "10B", "A:maj": "11B", "E:maj": "12B",
    "B:maj": "1B", "F#:maj": "2B", "C#:maj": "3B", "Ab:maj": "4B", "Eb:maj": "5B",
    "Bb:maj": "6B", "F:maj": "7B",
    "A:min": "8A", "E:min": "9A", "B:min": "10A", "F#:min": "11A", "C#:min": "12A",
    "G#:min": "1A", "D#:min": "2A", "A#:min": "3A", "F:min": "4A", "C:min": "5A",
    "G:min": "6A", "D:min": "7A"
}

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                          2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                          2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

MAJOR_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MINOR_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def normalize_note_index(note, mode):
    enh_major = {
        "C": "C", "B#": "C",
        "C#": "C#", "Db": "C#",
        "D": "D",
        "D#": "Eb", "Eb": "Eb",
        "E": "E", "Fb": "E",
        "F": "F", "E#": "F",
        "F#": "F#", "Gb": "F#",
        "G": "G",
        "G#": "Ab", "Ab": "Ab",
        "A": "A",
        "A#": "Bb", "Bb": "Bb",
        "B": "B", "Cb": "B",
    }
    enh_minor = {
        "A": "A",
        "A#": "A#", "Bb": "A#",
        "B": "B", "Cb": "B",
        "C": "C",
        "C#": "C#", "Db": "C#",
        "D": "D",
        "D#": "D#", "Eb": "D#",
        "E": "E", "Fb": "E",
        "F": "F",
        "F#": "F#", "Gb": "F#",
        "G": "G",
        "G#": "G#", "Ab": "G#",
    }
    target = enh_major if mode == 1 else enh_minor
    name = target.get(note, note)
    names = MAJOR_NAMES if mode == 1 else MINOR_NAMES
    try:
        return names.index(name)
    except ValueError:
        return None

def estimate_key_mode(y, sr):
    if es is None:
        return None, None
    try:
        key_extractor = es.KeyExtractor()
        key, scale, strength = key_extractor(y)
        note = key.split()[0]
        mode = 1 if scale.lower() == "major" else 0
        return normalize_note_index(note, mode), mode
    except Exception:
        return None, None

def detect_camelot(y, sr):
    key_idx, mode = estimate_key_mode(y, sr)
    if key_idx is None or mode is None:
        return "Unknown"

    if mode == 1:
        name = MAJOR_NAMES[key_idx]
        key_str = f"{name}:maj"
    else:
        name = MINOR_NAMES[key_idx]
        key_str = f"{name}:min"

    return Camelot_map.get(key_str, "Unknown")

