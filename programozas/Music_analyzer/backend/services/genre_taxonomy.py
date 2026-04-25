from __future__ import annotations

from typing import Optional

def normalize_genre_label(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower().replace("_", "-").replace(" ", "-")

def genre_family_for(value: Optional[str]) -> Optional[str]:
    genre = normalize_genre_label(value)
    if not genre:
        return None

    if "techno" in genre:
        return "techno"
    if "house" in genre:
        return "house"
    if genre in {"edm", "electro", "electronic", "electronica"}:
        return "electronic"
    if any(token in genre for token in ["trance", "hardstyle", "dubstep", "drum-and-bass", "dnb", "breakbeat"]):
        return "electronic"
    if any(token in genre for token in ["ambient", "chill", "chillout", "downtempo", "lo-fi", "lounge"]):
        return "chill"
    if any(token in genre for token in ["hip-hop", "rap", "trap"]):
        return "hip-hop"
    if any(token in genre for token in ["rock", "metal", "punk", "grunge", "emo"]):
        return "rock"
    if any(token in genre for token in ["pop", "dance-pop", "synth-pop"]):
        return "pop"
    if any(token in genre for token in ["jazz", "blues", "soul", "funk", "r-n-b", "rnb"]):
        return "jazz-soul"
    if any(token in genre for token in ["classical", "opera", "orchestral", "piano"]):
        return "classical"
    if any(token in genre for token in ["folk", "acoustic", "singer-songwriter", "country"]):
        return "acoustic-folk"

    return genre
