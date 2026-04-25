import os
import requests
from typing import Dict, List, Optional, Sequence, Tuple

RECOMMEND_URL = "https://api.reccobeats.com/v1/track/recommendation"

def _clamp(value: Optional[float], lo: float, hi: float) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, v))

def build_feature_filters(features: Optional[Dict]) -> Dict[str, float]:
    if not features:
        return {}
    filters: Dict[str, float] = {}

    valence = features.get("valence")
    if valence is None:
        valence = features.get("valence_local")
    v = _clamp(valence, 0.0, 1.0)
    if v is not None:
        filters["valence"] = v

    dance = features.get("danceability_score")
    if dance is None:
        dance = features.get("danceability_local")
    d = _clamp(dance, 0.0, 1.0)
    if d is not None:
        filters["danceability"] = d

    energy = features.get("energy")
    if energy is None:
        energy = features.get("energy_local")
    e = _clamp(energy, 0.0, 1.0)
    if e is not None:
        filters["energy"] = e

    tempo = _clamp(features.get("bpm"), 0.0, 250.0)
    if tempo is not None:
        filters["tempo"] = tempo

    loudness = features.get("rms")
    if loudness is not None:
        filters["loudness"] = _clamp(float(loudness) * 20.0, -60.0, 2.0)

    acoustic = features.get("acousticness")
    if acoustic is None:
        mood_ac = (features.get("mood_acoustic_top") or "").lower()
        if mood_ac == "acoustic":
            acoustic = 0.9
        elif mood_ac == "non_acoustic":
            acoustic = 0.1
    aco = _clamp(acoustic, 0.0, 1.0)
    if aco is not None:
        filters["acousticness"] = aco

    instr = features.get("instrumentalness")
    if instr is None:
        voice = (features.get("voice_instrumental_top") or "").lower()
        if voice == "instrumental":
            instr = 0.9
        elif voice == "voice":
            instr = 0.1
    ins = _clamp(instr, 0.0, 1.0)
    if ins is not None:
        filters["instrumentalness"] = ins

    speech = _clamp(features.get("speechiness"), 0.0, 1.0)
    if speech is not None:
        filters["speechiness"] = speech

    live = _clamp(features.get("liveness"), 0.0, 1.0)
    if live is not None:
        filters["liveness"] = live

    key = features.get("key")
    try:
        key_int = int(key) if key is not None else None
        if key_int is not None and -1 <= key_int <= 11:
            filters["key"] = key_int
    except Exception:
        pass

    mode = features.get("mode")
    if mode is None:
        mode = features.get("is_major")                    
    md = _clamp(mode, 0, 1)
    if md is not None:
        filters["mode"] = md

    popularity = features.get("spotify_popularity")
    pop = _clamp(popularity, 0, 100)
    if pop is not None:
        try:
            filters["popularity"] = int(round(pop))
        except Exception:
            pass

    return filters

def recommend_tracks(
    seeds: Sequence[str],
    *,
    size: int = 10,
    features: Optional[Dict] = None,
    negative: Optional[Sequence[str]] = None,
) -> Optional[Dict]:
    if not seeds:
        return None

    limit = max(1, min(size, 100))
    params: List[Tuple[str, str]] = [("size", str(limit)), ("limit", str(limit))]
    for sid in list(seeds)[:5]:
        if sid:
            params.append(("seeds", sid))
    if negative:
        for neg in negative:
            if neg:
                params.append(("negativeSeeds", neg))

    feature_params = build_feature_filters(features)
    for key, value in feature_params.items():
        params.append((key, str(value)))

    headers = {"Accept": "application/json"}

    try:
        resp = requests.get(RECOMMEND_URL, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            print("[reccobeats] recommend error:", resp.status_code, resp.text[:300])
            return None
        data = resp.json()
        data["_applied_filters"] = feature_params
        data["_seeds"] = list(seeds)
        return data
    except Exception as exc:
        print("[reccobeats] recommend request failed:", exc)
        return None
