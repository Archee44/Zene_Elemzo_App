import librosa
import numpy as np
import json
import os
from mutagen.easyid3 import EasyID3
import mutagen
from collections import Counter
import tkinter as tk
from tkinter import filedialog, messagebox

# Camelot-kód táblázatt
camelot_map = {
    'C':  '8B', 'C#': '3B', 'D':  '10B', 'D#': '5B', 'E':  '12B', 'F':  '7B',
    'F#': '2B', 'G':  '9B', 'G#': '4B', 'A':  '11B', 'A#': '6B', 'B':  '1B',
    'Cm': '5A', 'C#m':'12A','Dm': '7A',  'D#m':'2A', 'Em': '9A',  'Fm': '4A',
    'F#m':'11A','Gm': '6A', 'G#m':'1A',  'Am': '8A',  'A#m':'3A', 'Bm': '10A'
}

def detect_key_camelot(y, sr):
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    pitch_class = np.argmax(chroma_mean)
    pitch_names = ['C', 'C#', 'D', 'D#', 'E', 'F',
                   'F#', 'G', 'G#', 'A', 'A#', 'B']
    is_minor = librosa.feature.tonnetz(y=y, sr=sr).mean() < 0
    key_name = pitch_names[pitch_class] + ('m' if is_minor else '')
    return camelot_map.get(key_name, "Ismeretlen")

def analyze_bpm_advanced(y, sr):
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    threshold = np.percentile(rms, 50)
    mask = rms > threshold
    sample_mask = np.zeros(len(y), dtype=bool)
    for i, keep in enumerate(mask):
        start = i * hop_length
        end = min(start + hop_length, len(y))
        if keep:
            sample_mask[start:end] = True
    y_filtered = y[sample_mask]
    segment_length = sr * 15
    bpms = []
    for start in range(0, len(y_filtered), segment_length):
        segment = y_filtered[start:start+segment_length]
        if len(segment) < sr * 5:
            continue
        tempo, _ = librosa.beat.beat_track(y=segment, sr=sr)
        tempo_val = float(tempo[0]) if isinstance(tempo, (list, np.ndarray)) else float(tempo)
        bpms.append(int(round(tempo_val)))
    if not bpms:
        return None
    most_common_bpm = Counter(bpms).most_common(1)[0][0]
    if most_common_bpm < 80:
        most_common_bpm *= 2
    elif most_common_bpm > 180:
        most_common_bpm //= 2
    return most_common_bpm

def analyze_track(file_path):
    try:
        audiofile = EasyID3(file_path)
        title = audiofile.get("title", ["Ismeretlen"])[0]
        artist = audiofile.get("artist", ["Ismeretlen"])[0]
        genre = audiofile.get("genre", ["Ismeretlen"])[0]
    except mutagen.id3.ID3NoHeaderError:
        title = "Ismeretlen"
        artist = "Ismeretlen"
        genre = "Ismeretlen"
    y, sr = librosa.load(file_path)
    bpm = analyze_bpm_advanced(y, sr)
    camelot_key = detect_key_camelot(y, sr)
    return {
        "title": title,
        "artist": artist,
        "genre": genre,
        "bpm": bpm if bpm else 0,
        "camelot": camelot_key,
        "path": file_path
    }

def scan_folder(folder_path):
    tracks = []
    for file in os.listdir(folder_path):
        if file.endswith(".mp3"):
            full_path = os.path.join(folder_path, file)
            print(f"\nElemzés: {file}")
            track_data = analyze_track(full_path)
            tracks.append(track_data)
    with open("tracks.json", "w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=2, ensure_ascii=False)
    print("\n✅ Adatbázis frissítve: tracks.json")

def camelot_compatible(key1, key2):
    if key1 == "Ismeretlen" or key2 == "Ismeretlen":
        return False
    num1, letter1 = int(key1[:-1]), key1[-1]
    num2, letter2 = int(key2[:-1]), key2[-1]
    return (key1 == key2) or (letter1 == letter2 and abs(num1 - num2) in [1, 11])

def recommend_ai(input_bpm, input_key, input_genre, tracks, strict=False):
    scored = []
    for track in tracks:
        if strict and not camelot_compatible(track.get("camelot", "Ismeretlen"), input_key):
            continue  # ha szigorú, akkor kizárjuk

        score = 0
        bpm_diff = abs(track["bpm"] - input_bpm)
        score += max(0, 50 - bpm_diff * 5)

        if not strict:
            if camelot_compatible(track.get("camelot", "Ismeretlen"), input_key):
                score += 30
        else:
            score += 30  # ha már kompatibilis, adjuk meg a pontot

        if track.get("genre", "").lower() == input_genre.lower():
            score += 20

        scored.append((score, track))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [t for s, t in scored[:5]]


# GUI – 1. lépés: mappaválasztás és elemzés
def gui_step1():
    def select_folder():
        folder = filedialog.askdirectory(title="Válassz egy mappát a zenékhez")
        if not folder:
            messagebox.showinfo("Figyelem", "Nem választottál mappát.")
            return
        scan_folder(folder)
        messagebox.showinfo("Kész", "Elemzés kész, adatbázis mentve.")
        window.destroy()
        gui_step2()

    window = tk.Tk()
    window.title("Zeneelemzés – 1. lépés")
    window.geometry("400x200")
    tk.Label(window, text="Válassz egy mappát a zenék elemzéséhez", font=("Arial", 12)).pack(pady=20)
    tk.Button(window, text="Mappa kiválasztása", command=select_folder, font=("Arial", 11)).pack(pady=10)
    window.mainloop()



# GUI – 2. lépés: zenekiválasztás és ajánlás
def gui_step2():
    with open("tracks.json", "r", encoding="utf-8") as f:
        tracks = json.load(f)

    def show_recommendation():
        selection = listbox.curselection()
        if not selection:
            messagebox.showinfo("Figyelem", "Nem választottál zenét.")
            return
        index = selection[0]
        selected = tracks[index]
        bpm = selected["bpm"]
        key = selected["camelot"]
        genre = selected["genre"]
        strict = var_strict.get() == 1  # kapcsoló állapota

        recommended = recommend_ai(bpm, key, genre, tracks, strict)
        if not recommended:
            messagebox.showinfo("Nincs találat", "Nem találtunk kompatibilis zenét.")
            return
        result_text = "\n".join([f"{t['title']} - {t['artist']} ({t['bpm']} BPM, {t['camelot']})" for t in recommended])
        messagebox.showinfo("Ajánlott zenék", result_text)

    window = tk.Tk()
    window.title("Ajánlórendszer – 2. lépés")
    window.geometry("500x450")

    tk.Label(window, text="Válassz egy zenét az ajánláshoz", font=("Arial", 12)).pack(pady=10)

    listbox = tk.Listbox(window, width=60, height=15)
    for track in tracks:
        listbox.insert(tk.END, f"{track['title']} - {track['artist']}")
    listbox.pack(pady=10)

    var_strict = tk.IntVar()
    tk.Checkbutton(window, text="Csak harmonikus ajánlásokat kérek", variable=var_strict).pack()

    tk.Button(window, text="Ajánlás kérése", command=show_recommendation, font=("Arial", 11)).pack(pady=10)

    window.mainloop()


# Indítás
if __name__ == "__main__":
    gui_step1()
