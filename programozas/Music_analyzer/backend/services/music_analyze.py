from typing import Optional, Tuple, List, Dict
import os
import re
import sys
import json
import numpy as np

try:
    import essentia
    import essentia.standard as es
except ImportError:
    es = None
else:
    try:
        import essentia as _ess
        _ess.log.setLevel(_ess.EVerbosity.ERROR)
    except Exception:
        pass

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from dotenv import load_dotenv
from backend.services.camelot import detect_camelot
from backend.services.genre_model import predict_genres
from backend.services.approachability_model import predict_approachability
from backend.services.danceability_model import predict_danceability
from backend.services.engagement_model import predict_engagement
from backend.services.valence_arousal_model import predict_valence_arousal
from backend.services.mood_mirex_model import predict_mood_mirex
from backend.services.tag_models import (
    predict_bright_dark,
    predict_mood_acoustic,
    predict_voice_instrumental,
)

load_dotenv()

upload_folder = "./uploads"

def cleaned_title(title: str) -> str:
    title = re.sub(r"[\(\[].*?[\)\]]", "", title)
    title = re.sub(r"\b(official music video|official video|music video|video clip|audio|hq|id\d{3,}|v\d+|mp3|flac|mp3juices\.cc|mp3j\.cc|y2mate\.com|soundcloud rip|youtube download)\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*(?:ft\.?|feat\.?|featuring)\s+.+$", "", title, flags=re.IGNORECASE)
    title = title.replace("_", " ")
    title = re.sub(r"\s+", " ", title)
    return title.strip()

def compute_local_features(y: np.ndarray, sr: int) -> dict:
    out = {}
    if es is None:
        return {
            "spectral_centroid_mean": None,
            "spectral_centroid_std": None,
            "spectral_rolloff_85": None,
            "zcr_mean": None,
            "onset_rate": None,
            "harmonic_percussive_ratio": None,
            "chroma_var": None,
            "rms_mean": None,
        }

    N = 2048
    H = 512
    window = es.Windowing(type='hann')
    spectrum = es.Spectrum()
    flux_algo = es.Flux()
    zcr_algo = es.ZeroCrossingRate()
    rms_algo = es.RMS()
    peaks = es.SpectralPeaks(maxPeaks=50, minFrequency=20.0, maxFrequency=sr / 2.0)
    hpcp_algo = es.HPCP(size=12)

    centroids = []
    rolloffs = []
    zcrs = []
    flatnesses = []
    rms_vals = []
    hpcp_frames = []
    flux_vals = []
    bw_vals = []
    prev_spec = None

    for frame in es.FrameGenerator(y, frameSize=N, hopSize=H, startFromZero=True):
        zcrs.append(float(zcr_algo(frame)))
        rms_vals.append(float(rms_algo(frame)))
        w = window(frame)
        spec = spectrum(w)
        mag = np.asarray(spec)
        if mag.size == 0 or float(mag.sum()) == 0.0:
            continue
        if prev_spec is not None:
            try:
                flux_vals.append(float(flux_algo(prev_spec, mag)))
            except Exception:
                pass
        prev_spec = mag
        freqs = np.linspace(0.0, sr / 2.0, num=len(mag), endpoint=True)
        c = float((freqs * mag).sum() / (mag.sum() + 1e-12))
        centroids.append(c)
        bw = float(np.sqrt(((np.square(freqs - c) * mag).sum()) / (mag.sum() + 1e-12)))
        bw_vals.append(bw)
        cumsum = np.cumsum(mag)
        thr = 0.85 * cumsum[-1]
        idx = int(np.searchsorted(cumsum, thr))
        denom = max(len(mag) - 1, 1)
        roll_freq = float(idx) * (sr / 2.0) / denom
        rolloffs.append(roll_freq)
        gm = float(np.exp(np.mean(np.log(mag + 1e-12))))
        am = float(np.mean(mag + 1e-12))
        flatnesses.append(gm / am)
        f, m = peaks(spec)
        if len(f) > 0:
            h = hpcp_algo(f, m)
            hpcp_frames.append(np.asarray(h))

    onset_rate = None
    try:
        onset_rate = float(es.OnsetRate()(y))
    except Exception:
        onset_rate = None

    out["spectral_centroid_mean"] = float(np.mean(centroids)) if centroids else None
    out["spectral_centroid_std"] = float(np.std(centroids)) if centroids else None
    out["spectral_rolloff_85"] = float(np.mean(rolloffs)) if rolloffs else None
    out["zcr_mean"] = float(np.mean(zcrs)) if zcrs else None
    out["onset_rate"] = onset_rate
    out["rms_mean"] = float(np.mean(rms_vals)) if rms_vals else None
    out["spectral_flux_mean"] = float(np.mean(flux_vals)) if flux_vals else None
    out["spectral_bandwidth_mean"] = float(np.mean(bw_vals)) if bw_vals else None

    hpr = None
    if flatnesses:
        flat_mean = float(np.mean(flatnesses))
        hpr = float(1.0 / (flat_mean + 1e-8))
    out["harmonic_percussive_ratio"] = hpr

    chroma_var = None
    if hpcp_frames:
        hpcp_arr = np.vstack(hpcp_frames)
        hpcp_arr_T = hpcp_arr.T
        chroma_var = float(np.mean(np.var(hpcp_arr_T, axis=1)))
        out["hpcp_mean"] = [float(x) for x in list(np.mean(hpcp_arr, axis=0))]
    out["chroma_var"] = chroma_var

    return out

def analyze_music(file_path: str, user_token=None):
    if es is None:
        raise RuntimeError("Essentia is not installed. Please run in Docker.")

    loader = es.MonoLoader(filename=file_path, sampleRate=44100)
    y = loader()
    sr = 44100

    duration = float(len(y) / sr) if sr > 0 else 0.0
    tempo_confidence = None
    beat_count = None
    try:
        bpm_raw = es.RhythmExtractor2013()(y)
        bpm = int(round(float(bpm_raw[0])))
        ticks = bpm_raw[1]
        tempo_confidence = float(bpm_raw[2]) if len(bpm_raw) > 2 else None
        beat_count = int(len(ticks)) if ticks is not None else None
    except Exception:
        bpm = 0

    local_feats = compute_local_features(y, sr)
    rms = local_feats.get("rms_mean") or 0.0
    camelot = detect_camelot(y, sr)

    danceability_essentia = None
    try:
        dfa_dance, _ = es.Danceability()(y)
        # Same DFA-based algorithm and rescale used by AcousticBrainz/MTG-Jamendo
        # (see import_from_jamendo.py), so uploaded and catalog-seeded songs share
        # one comparable scale. A hard clamp to 1.0 instead of a rescale would
        # saturate most real tracks at the ceiling, since raw values commonly run
        # well above 1.0.
        danceability_essentia = min(max(float(dfa_dance), 0.0), 2.5) / 2.5
    except Exception:
        pass
    key_strength = None
    is_major = None
    try:
        key_ex = es.KeyExtractor()
        key_name, scale, strength = key_ex(y)
        key_strength = float(strength)
        is_major = 1 if str(scale).lower() == "major" else 0
    except Exception:
        pass

    def classify_genre_detailed(bpm: int, feats: dict, tempo_conf: Optional[float], rg_db: Optional[float]):
        sc = feats.get("spectral_centroid_mean") or 0.0
        roll = feats.get("spectral_rolloff_85") or 0.0
        zcr = feats.get("zcr_mean") or 0.0
        onset = feats.get("onset_rate") or 0.0
        hpr = feats.get("harmonic_percussive_ratio") or 1.0
        chroma_var = feats.get("chroma_var") or 0.0
        flux = feats.get("spectral_flux_mean") or 0.0
        bw = feats.get("spectral_bandwidth_mean") or 0.0
        rms_mean = feats.get("rms_mean") or 0.0

        sc_n = sc / 4000.0
        roll_n = roll / 8000.0
        zcr_n = zcr * 10.0
        onset_n = min(onset / 6.0, 1.5)
        hpr_n = min(hpr, 3.0)
        chroma_n = min(chroma_var, 1.5)
        flux_n = min(flux / 5.0, 1.0)
        bw_n = min(bw / 3000.0, 1.0)
        rms_n = min(max(rms_mean * 10.0, 0.0), 1.5)
        tempo_n = max(0.0, 1.0 - (abs((bpm or 0) - 120) / 120.0))
        tc_n = min(max((tempo_conf or 0.0), 0.0), 1.0)
        rg_n = min(max(((rg_db or -12.0) + 18.0) / 24.0, 0.0), 1.0)

        cand: List[Tuple[str, float]] = []

        score_pop = 0.0
        if 90 <= (bpm or 0) <= 135:
            score_pop += 0.6
        score_pop += 0.3 * (1.0 - zcr_n) + 0.25 * (1.0 - roll_n) + 0.3 * chroma_n + 0.15 * tempo_n
        cand.append(("Pop", score_pop))

        score_rock = 0.0
        if 110 <= (bpm or 0) <= 180:
            score_rock += 0.5
        score_rock += 0.45 * sc_n + 0.35 * roll_n + 0.25 * zcr_n + 0.2 * flux_n + 0.2 * (rms_n / 1.5)
        cand.append(("Rock", score_rock))

        score_metal = 0.0
        if (bpm or 0) >= 140:
            score_metal += 0.5
        score_metal += 0.55 * roll_n + 0.5 * sc_n + 0.35 * zcr_n + 0.25 * flux_n + 0.2 * bw_n
        cand.append(("Metal", score_metal))

        score_rap = 0.0
        if 70 <= (bpm or 0) <= 110:
            score_rap += 0.6
        score_rap += 0.4 * (1.1 - sc_n) + 0.25 * zcr_n + 0.15 * bw_n + 0.15 * (1.0 - onset_n)
        cand.append(("Hip-Hop/Rap", score_rap))

        score_dance = 0.0
        if 118 <= (bpm or 0) <= 135:
            score_dance += 0.8
        score_dance += 0.35 * onset_n + 0.3 * flux_n + 0.25 * (1.0 / max(hpr_n, 0.4)) + 0.2 * tc_n
        cand.append(("Dance/Electronic", score_dance))

        score_acoustic = 0.0
        if (bpm or 0) <= 120:
            score_acoustic += 0.3
        score_acoustic += 0.45 * (hpr_n / 2.0) + 0.35 * (1.2 - sc_n) + 0.2 * (1.0 - onset_n)
        cand.append(("Acoustic/Folk", score_acoustic))

        score_jazz = 0.0
        if 80 <= (bpm or 0) <= 160:
            score_jazz += 0.2
        score_jazz += 0.45 * (hpr_n / 2.0) + 0.35 * chroma_n + 0.15 * (1.0 - onset_n)
        cand.append(("Jazz/Blues", score_jazz))

        score_classical = 0.0
        if (bpm or 0) <= 100:
            score_classical += 0.25
        score_classical += 0.5 * (hpr_n / 2.0) + 0.35 * (1.3 - sc_n) + 0.25 * (1.0 - onset_n)
        cand.append(("Classical/Orchestral", score_classical))

        score_rnb = 0.0
        if 60 <= (bpm or 0) <= 105 or 120 <= (bpm or 0) <= 150:
            score_rnb += 0.2
        score_rnb += 0.35 * (1.0 - sc_n) + 0.25 * (1.0 - onset_n) + 0.2 * chroma_n + 0.2 * (rms_n / 1.5)
        cand.append(("R&B/Soul", score_rnb))

        score_latin = 0.0
        if 85 <= (bpm or 0) <= 110:
            score_latin += 0.3
        score_latin += 0.3 * onset_n + 0.3 * flux_n + 0.2 * bw_n + 0.1 * (1.0 - sc_n)
        cand.append(("Latin/Reggaeton", score_latin))

        max_score = max([s for _, s in cand]) if cand else 1.0
        norm = [(g, float(s / max_score) if max_score > 0 else 0.0) for g, s in cand]
        norm_sorted = sorted(norm, key=lambda x: x[1], reverse=True)
        top = norm_sorted[0][0] if norm_sorted else "Unknown"
        return top, norm_sorted

    genre_detailed, genre_detailed_candidates = classify_genre_detailed(bpm, local_feats, tempo_confidence, replaygain_db if 'replaygain_db' in locals() else None)

    artist = "Unknown Artist"
    genre = "Unknown Genre"
    title = "Unknown Title"

    if es is not None:
        try:
            meta = es.MetadataReader(filename=file_path)()
            title_tag, artist_tag, album_artist, album, genre_tag = meta[0], meta[1], meta[2], meta[3], meta[4]
            if title_tag:
                title = cleaned_title(str(title_tag))
            if artist_tag:
                artist = str(artist_tag)
            elif album_artist:
                artist = str(album_artist)
            if genre_tag:
                genre = str(genre_tag)
        except Exception as e:
            print("Essentia metadata error:", e)

    if artist == "Unknown Artist" or title == "Unknown Title":
        try:
            audio = MP3(file_path, ID3=ID3)
            artist_tag = audio.get("TPE1")
            genre_tag = audio.get("TCON")
            title_tag = audio.get("TIT2")

            if artist_tag and artist_tag.text:
                artist = artist_tag.text[0]
            if genre_tag and genre_tag.text:
                genre = genre_tag.text[0]
            if title_tag and title_tag.text:
                title = cleaned_title(title_tag.text[0])
        except Exception as e:
            print("Metadata error:", str(e))

    if artist == "Unknown Artist" or title == "Unknown Title":
        filename = os.path.basename(file_path)
        name_only = os.path.splitext(filename)[0]
        for sep in ("-", "_"):
            parts = [p.strip().replace("_", " ") for p in name_only.split(sep) if p.strip()]
            if len(parts) >= 2:
                if artist == "Unknown Artist":
                    artist = parts[0]
                if title == "Unknown Title":
                    title = cleaned_title(" ".join(parts[1:]))
                break

    replaygain_db = None
    try:
        rg = es.ReplayGain()
        g, p = rg(y)
        replaygain_db = float(g)
    except Exception:
        pass

    sc = local_feats.get("spectral_centroid_mean") or 0.0
    roll = local_feats.get("spectral_rolloff_85") or 0.0
    onset_rate = local_feats.get("onset_rate") or 0.0
    flux = local_feats.get("spectral_flux_mean") or 0.0
    sc_n = sc / 4000.0
    roll_n = roll / 8000.0
    rms_n = min(max(rms * 10.0, 0.0), 1.5) / 1.5
    onset_n = min(onset_rate / 6.0, 1.0)
    flux_n = min(flux / 5.0, 1.0)
    tempo_n = max(0.0, 1.0 - (abs((bpm or 0) - 120) / 120.0))
    tempo_conf_n = min(max((tempo_confidence or 0.0), 0.0), 1.0)
    energy_local = float(np.clip(0.4 * rms_n + 0.3 * roll_n + 0.3 * sc_n, 0.0, 1.0))
    danceability_local = float(np.clip(0.45 * tempo_n + 0.25 * onset_n + 0.2 * flux_n + 0.1 * tempo_conf_n, 0.0, 1.0))
    major_bonus = 0.15 if is_major == 1 else -0.05 if is_major == 0 else 0.0
    valence_local = float(np.clip(0.6 * sc_n + 0.4 * (local_feats.get("chroma_var") or 0.0) + major_bonus, 0.0, 1.0))

    model_genres = predict_genres(file_path)
    approach = predict_approachability(file_path)
    danceab = predict_danceability(file_path)
    engage = predict_engagement(file_path)
    va = predict_valence_arousal(file_path)
    mirex = predict_mood_mirex(file_path)
    bright_dark = predict_bright_dark(file_path)
    voice_inst = predict_voice_instrumental(file_path)
    mood_acoustic = predict_mood_acoustic(file_path)

    preferred_genre = None
    preferred_macro = None
    if model_genres and model_genres.get("genre_model"):
        preferred_genre = model_genres.get("genre_model")
        preferred_macro = model_genres.get("genre_model_macro")

    cover_file = None
    try:
        audio_tags = MP3(file_path, ID3=ID3)
        if audio_tags.tags:
            base_dir = os.path.dirname(file_path)
            for f in os.listdir(base_dir):
                if f.endswith(("_cover.jpg", "_cover.jpeg", "_cover.png")):
                    try:
                        os.remove(os.path.join(base_dir, f))
                    except Exception:
                        pass

            for tag in audio_tags.tags.values():
                if isinstance(tag, APIC) and tag.data:
                    mime = (tag.mime or "image/jpeg").lower()
                    ext = "png" if "png" in mime else "jpg"
                    base = os.path.splitext(os.path.basename(file_path))[0]
                    cover_name = f"{base}_cover.{ext}"
                    out_path = os.path.join(os.path.dirname(file_path), cover_name)
                    with open(out_path, "wb") as f:
                        f.write(tag.data)
                    cover_file = cover_name
                    break
    except Exception:
        cover_file = None

    result = {
        "title": title,
        "artist": artist,
        "genre": preferred_macro or preferred_genre or (genre if genre != "Unknown Genre" else genre_detailed),
        "genre_detailed": preferred_genre or genre_detailed,
        "genre_model": model_genres.get("genre_model"),
        "genre_model_candidates": model_genres.get("genre_model_candidates"),
        "genre_model_macro": model_genres.get("genre_model_macro"),
        "genre_model_name": model_genres.get("genre_model_name"),
        "genre_source": (
            f"model:{model_genres.get('genre_model_name')}" if preferred_genre else (
                "local_heuristic" if genre == "Unknown Genre" else "tag_or_filename"
            )
        ),
        "duration": float(duration),
        "bpm": bpm,
        "rms": rms,
        "camelot": camelot,
        "tempo_confidence": tempo_confidence,
        "beat_count": beat_count,
        "replaygain_db": replaygain_db,
        "energy_local": energy_local,
        "danceability_local": danceability_local,
        "danceability_essentia": danceability_essentia,
        "valence_local": valence_local,
        "key_strength": key_strength,
        **local_feats,
        "genre_detailed_candidates": [{"label": g, "score": float(s)} for g, s in genre_detailed_candidates]
    }
    if cover_file:
        result["cover"] = cover_file
    if approach:
        result["approachability_model_name"] = approach.get("model_name")
        if approach.get("type") == "classification":
            result["approachability_top"] = approach.get("top")
            result["approachability_candidates"] = [
                {"label": l, "score": float(s)} for l, s in (approach.get("candidates") or [])
            ]
        else:
            result["approachability_score"] = approach.get("score")

    if danceab:
        result["danceability_model_name"] = danceab.get("model_name")
        if danceab.get("type") == "regression":
            result["danceability_score"] = danceab.get("score")
        else:
            result["danceability_top"] = danceab.get("top")
            result["danceability_candidates"] = [
                {"label": l, "score": float(s)} for l, s in (danceab.get("candidates") or [])
            ]

    if engage:
        result["engagement_model_name"] = engage.get("model_name")
        if engage.get("type") == "regression":
            result["engagement_score"] = engage.get("score")
        else:
            result["engagement_top"] = engage.get("top")
            result["engagement_candidates"] = [
                {"label": l, "score": float(s)} for l, s in (engage.get("candidates") or [])
            ]

    if va:
        result["valence_arousal_model_name"] = va.get("model_name")
        if va.get("arousal") is not None:
            result["arousal"] = float(va.get("arousal"))
        if va.get("valence") is not None:
            result["valence"] = float(va.get("valence"))
        if va.get("arousal_std") is not None:
            result["arousal_std"] = float(va.get("arousal_std"))
        if va.get("valence_std") is not None:
            result["valence_std"] = float(va.get("valence_std"))
        if va.get("count") is not None:
            result["va_window_count"] = int(va.get("count"))

    if mirex:
        result["mood_mirex_model_name"] = mirex.get("model_name")
        result["mood_mirex_top"] = mirex.get("top")
        result["mood_mirex_candidates"] = [
            {"label": l, "score": float(s)} for l, s in (mirex.get("candidates") or [])
        ]
    if bright_dark:
        result["bright_dark_model_name"] = bright_dark.get("model_name")
        result["bright_dark_top"] = bright_dark.get("top")
        result["bright_dark_candidates"] = [
            {"label": l, "score": float(s)} for l, s in (bright_dark.get("candidates") or [])
        ]
    if voice_inst:
        result["voice_instrumental_model_name"] = voice_inst.get("model_name")
        result["voice_instrumental_top"] = voice_inst.get("top")
        result["voice_instrumental_candidates"] = [
            {"label": l, "score": float(s)} for l, s in (voice_inst.get("candidates") or [])
        ]
    if mood_acoustic:
        result["mood_acoustic_model_name"] = mood_acoustic.get("model_name")
        result["mood_acoustic_top"] = mood_acoustic.get("top")
        result["mood_acoustic_candidates"] = [
            {"label": l, "score": float(s)} for l, s in (mood_acoustic.get("candidates") or [])
        ]
    return result

if __name__ == "__main__":
    file_path = sys.argv[1]
    result = analyze_music(file_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
