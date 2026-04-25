import { useState } from "react";
import { TextInput, Button, Card, Box, Image, Loader, SegmentedControl, Text, Select, Progress, Tabs } from '@mantine/core';
import { useMantineColorScheme } from '@mantine/core';
import { IconMusic, IconSearch, IconUser } from '@tabler/icons-react';

export default function Search() {
  const [snippet, setSnippet] = useState("");
  const [songs, setSongs] = useState([]);
  const [index, setIndex] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState(false);
  const [loadingDiscover, setLoadingDiscover] = useState(false);
  const [progress, setProgress] = useState(0);
  const [discoverTracks, setDiscoverTracks] = useState([]);
  const [artist, setArtist] = useState(null);
  const [mode, setMode] = useState("discover");

  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === 'dark';

  const [explicitMode, setExplicitMode] = useState("any");
  const [discoverGenre, setDiscoverGenre] = useState("any");
  const [popularityMode, setPopularityMode] = useState("any");
  const [releaseRange, setReleaseRange] = useState("any");
  const [discoverMood, setDiscoverMood] = useState("any");
  const GENRES = [
  { value: "Pop", label: "Pop" },
  { value: "Rock", label: "Rock" },
  { value: "Metal", label: "Metal" },
  { value: "Jazz", label: "Jazz" },
  { value: "Hip-Hop", label: "Hip-hop" },
  { value: "Electronic", label: "EDM / Electronic" },
  { value: "K-Pop", label: "K-Pop" },
  { value: "Classical", label: "Klasszikus" },
  { value: "Country", label: "Country" },
  { value: "Instrumental", label: "Instrumentális" },
  { value: "Latin", label: "Latin" },
  { value: "Rap", label: "Rap" },
  { value: "Hardstyle", label: "Hardstyle" },
  ];

  const handleDiscoverSearch = async () => {
    setError("");
    setLoadingDiscover(true);
    setProgress(0);
    setDiscoverTracks([]);
    setIndex(0);
    
    let progressInterval;
    let showTimeout;
    const startTime = Date.now();
    

    try {
      showTimeout = setTimeout(() => {
      }, 150);
      progressInterval = window.setInterval(async () => {
      try {
          const resProg = await fetch("http://127.0.0.1:5000/api/music/search-discover/progress");
          if (!resProg.ok) return;
          const dataProg = await resProg.json();
          if (typeof dataProg.percent === "number") { setProgress((prev) => {
            const next = Math.max(prev, dataProg.percent);
            return Math.max(next, 5);
          })}} catch (err) { console.error("Progress fetch error:", err) }}, 400);
      const res = await fetch("http://127.0.0.1:5000/api/music/search-discover", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ genre: discoverGenre, popularityMode, releaseRange, mood: discoverMood, explicitMode })});
      if (!res.ok) { setError("Hiba a discover keresésnél"); return }
      const data = await res.json();
      const tracks = data.tracks || [];

      if (!tracks.length) { setError( "Nem találtunk a beállításoknak megfelelő zenét. Próbálj lazább szűrést!") }
      setDiscoverTracks(tracks);
      setIndex(0);
      setProgress(100);
      const elapsed = Date.now() - startTime;
      const minDisplay = 300;
      const waitMore = Math.max(0, minDisplay - elapsed);

      await new Promise((resolve) => setTimeout(resolve, waitMore));
    } catch (e) {
      console.error(e);
      setError("Hiba történt a discover keresés során.");
    } finally {
      if (progressInterval) clearInterval(progressInterval);
      if (showTimeout) clearTimeout(showTimeout);
      setLoadingDiscover(false);
    }
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    setError("");
    setSongs([]);
    setArtist(null);
    setLoading(true);

    try {
      if (mode === "lyrics") {
        const res = await fetch("http://127.0.0.1:5000/api/music/search-lyrics", {method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ snippet })});
        const data = await res.json();

        if (res.status === 404 || (Array.isArray(data.songs) && data.songs.length === 0)) {
          setError("Nem található ilyen dalszövegű zene.");
          setSongs([]);
        } else if (data.songs) {
          setSongs(data.songs);
          setIndex(0);
        } else if (data.error) {
          setError("Nem adott meg dalszöveget");
        }
      } else if (mode === "artist") {
        const res = await fetch("http://127.0.0.1:5000/api/music/search-artist", {method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: snippet })});
        const data = await res.json();
        if (!res.ok || data.error) {
          setError(data.error || "Nem található ilyen előadó.");
        } else {
          setArtist(data);
        }
      }
    } catch (e) {
      setError("Hálózatihiba történt.");
    } finally {
      setLoading(false);
    }
  };

  const line = (label, value, extra = null) => (<div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", border: dark ? "1px solid #483d8b" : "1px solid #FFD966", textAlign: "center"}}>
                      <div style={{ width: 160, minWidth: 140, fontWeight: 600, opacity: 0.85, textAlign: "left"}}>{label}</div>
                      <div style={{ flex: 1, textAlign: "center" }}>{value || "—"}</div>{extra}</div>);

  const handleNext = () => { if (index < songs.length - 1) setIndex(index + 1); };
  const handlePrev = () => { if (index > 0) setIndex(index - 1); };
  const currentSong = songs[index];

  const resetLyrics = () => { setSnippet("");setSongs([]); setIndex(0) };
  const resetArtist = () => { setArtist(null);setSnippet("") };
  const resetDiscover = () => { setDiscoverGenre("any"); setPopularityMode("any"); setDiscoverMood("any"); setReleaseRange("any"); setExplicitMode("any"); setDiscoverTracks([]); setError(""); setIndex(0) };

  const goToArtist = async (artistName) => { setMode("artist"); setSnippet(artistName); setLoading(true); setError(""); setSongs([]); setArtist(null);
    try {
      const res = await fetch("http://127.0.0.1:5000/api/music/search-artist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: artistName })});
      const data = await res.json();
      if (!res.ok || data.error) { setError(data.error || "Nem található ilyen előadó.");}
      else {setArtist(data);}}
    catch (err) { setError("Hiba történt az előadó lekérdezésénél.");}
      finally {setLoading(false);}
    };
  
  const goToMusic = async (musicTitle, artistNameFromRow = "") => {
    const finalArtistName = artistNameFromRow || artist?.name || "";
    const snippetText = finalArtistName ? `${finalArtistName} - ${musicTitle}`: musicTitle;
    setMode("lyrics"); setSnippet(snippetText); setLoading(true); setError(""); setSongs([]); setIndex(0);
    try {
      const res = await fetch("http://127.0.0.1:5000/api/music/search-lyrics", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ snippet: snippetText }) });
      const data = await res.json();
      if (!res.ok || data.error) {setError(data.error || "Nem található ilyen zene.");}
      else {setSongs(data.songs || []);setIndex(0);}} 
    catch (err) { console.error(err);setError("Hiba történt a zene lekérdezésénél.");}
      finally {setLoading(false);}
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minHeight: "calc(100vh - 100px)", marginTop: "50px" }}>
      <Card shadow="xl" padding="xl" radius="lg" withBorder
        style={{ width: "100%", maxWidth: 900, backgroundColor: dark ? "#0C1A2A" : "#FFF8E7", color: dark ? "#FFFFFF" : "#0C1A2A",
        borderColor: dark ? "#483d8b" : "#FFD966" }}>
        <SegmentedControl value={mode} onChange={(val) => { setMode(val); setSongs([]); setArtist(null); setError(""); resetDiscover(); resetLyrics(); resetArtist(); }} data={[
          { value: "discover", label: (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontWeight: 600 }}><IconSearch size={18} /><span>Felfedező</span></div>)}, 
          { value: "lyrics", label: (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontWeight: 600 }}><IconMusic size={18} /><span>Zene</span></div>)}, 
          { value: "artist", label: (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontWeight: 600, }}><IconUser size={18} /><span>Zeneszerző</span></div>)}]}
          color={dark ? "#483d8b" : "#FFD966"} radius="md" size="lg" fullWidth styles={{ label: { color: dark ? "#FFF" : "#0C1A2A", fontWeight: 600, fontSize: "1rem" }, control: { height: 40, transition: "all 0.2s ease" }}}/>
        <h1 style={{ textAlign: "center", marginBottom: 32, fontSize: "3rem", fontWeight: 700 }}>
          {mode === "lyrics" ? "Zenekereső" : mode === "artist" ? "Zeneszerző kereső" : "Felfedező"}
        </h1>
        {mode !== 'discover' &&(
        <form onSubmit={handleSearch} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <Box style={{ position: "relative" }}>
            <Box style={{ position: "absolute", top: 0, left: 0, width: 55, height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
              backgroundColor: dark ? "#483d8b" : "#FFD966", borderTopLeftRadius: 10, borderBottomLeftRadius: 10, zIndex: 1 }}>
              <Image src="/icons/New_MeloDive.png" width={28} height={28} radius="md" />
            </Box>

            <TextInput value={snippet} onChange={(e) => setSnippet(e.target.value)} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} placeholder={mode === 'lyrics' ? "Írj be egy dalszövegrészletet..." : "Írj be egy zeneszerző nevét"} size="lg" radius="md"
              styles={{ input: { paddingLeft: 65, fontSize: "1.1rem", height: "60px", backgroundColor: dark ? "#2C2E33" : "#FFFFFF", color: dark ? "#FFFFFF" : "#0C1A2A", 
              borderColor: focused ? (dark ? "#a78bfa" : "#FFD966") : (dark ? "#483d8b" : "#FFD966"),
              boxShadow: focused ? (dark ? "0 0 8px 2px rgba(167, 139, 250, 0.5)" : "0 0 8px 2px rgba(255, 217, 102, 0.6)") : "none", transition: "box-shadow 0.3s ease, border-color 0.3s ease"
              }}}/>
          </Box>
        </form>
        )}
        {loading && (
          <div style={{ textAlign: "center", marginTop: 24 }}>
            <Loader color={dark ? "violet" : "yellow"} />
          </div>
        )}
        {mode === "discover" && (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 24 }}>
            <div
              style={{ width: "min(800px, 95%)", padding: 24, borderRadius: 16, background: dark ? "rgba(72, 61, 139, 0.3)" : "rgba(255, 217, 102, 0.3)", border: dark ? "3px solid #483d8b" : "3px solid #FFD966",
                backdropFilter: "blur(6px)", boxShadow: dark ? "0 6px 24px rgba(0,0,0,0.35)" : "0 8px 24px rgba(12,26,42,0.08)" }}>
              <p style={{ margin: "0 0 16px 0", fontSize: 14, opacity: 0.8, textAlign: "center", }}>
                Add meg a kívánt szűrőket a zene felfedezéséhez.
              </p>

              <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: 16, }}>
                <div style={{ gridColumn: "1 / 3" }}>
                  <Text size="sm" fw={500} mb={4} align="center">
                    Műfaj
                  </Text>
                  <Select onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} styles={{ input: { textAlign:"center", fontSize: "1rem", height: "50px", backgroundColor: dark ? "#171429" : "#FFF8E7", color: dark ? "#FFFFFF" : "#0C1A2A", 
                    borderColor: focused ? (dark ? "#9271f7ff" : "#FFD966") : (dark ? "#483d8b" : "#FFD966"), boxShadow: focused ? (dark ? "0 0 8px 2px rgba(167, 139, 250, 0.5)" : "0 0 8px 2px rgba(255, 217, 102, 0.6)") : "none" },
                    dropdown: { backgroundColor: dark ? "#1E1B2E" : "#FFF8E7", borderColor: dark ? "#483d8b" : "#FFD966" }, item: {
                    backgroundColor: dark ? "#1E1B2E" : "#FFF8E7", color: dark ? "#FFFFFF" : "#0C1A2A", '&[data-hovered]': { backgroundColor: dark ? "#2B2542" : "#FFEFB3"}, '&[data-selected]': { backgroundColor: dark ? "#483d8b" : "#FFD966", color: dark ? "#FFFFFF" : "#0C1A2A" }},
                    clearButton: { color: dark ? "#FFFFFF" : "#0C1A2A", backgroundColor: dark ? "#171429" : "#FFEFB3", borderRadius: 6 }
                    }} placeholder="Válassz egy műfajt" data={GENRES} value={discoverGenre} onChange={setDiscoverGenre} clearable/>
                </div>
                <div>
                  <Text size="sm" fw={500} mb={4} align="center">
                    Népszerűség
                  </Text>
                  <SegmentedControl radius="md" fullWidth styles={{ root: { border: `2px solid ${dark ? "#483d8b" : "#FFD966"}`, padding: 2, borderRadius: 10, backgroundColor: dark ? "#171429" : "#FFF8E7" },
                  indicator: { backgroundColor: dark ? "#483d8b" : "#FFC56E", borderRadius: 8 }, label: { color: dark ? "#FFFFFF" : "#0C1A2A", fontWeight: 600, fontSize: "1rem" }, control: { transition: "all 0.2s ease" }}} value={popularityMode} onChange={setPopularityMode} data={[ { label: "Mindegy", value: "any" }, { label: "Népszerű", value: "popular" }, { label: "Kevésbé ismert", value: "unpopular" }]}/>
                </div>
                <div>
                  <Text size="sm" fw={500} mb={4} align="center">
                    Explicit tartalom
                  </Text>
                  <SegmentedControl radius="md" fullWidth styles={{ root: { border: `2px solid ${dark ? "#483d8b" : "#FFD966"}`, padding: 2, borderRadius: 10, backgroundColor: dark ? "#171429" : "#FFF8E7" },
                  indicator: { backgroundColor: dark ? "#483d8b" : "#FFC56E", borderRadius: 8 }, label: { color: dark ? "#FFFFFF" : "#0C1A2A", fontWeight: 600, fontSize: "1rem" }, control: { transition: "all 0.2s ease" }}} value={explicitMode} onChange={setExplicitMode} data={[ { label: "Mindegy", value: "any" }, { label: "Tiszta", value: "clean" }, { label: "Explicit", value: "explicit" },]}/>
                </div>
                <div style={{ gridColumn: "1 / 3", justifySelf: "center", maxWidth: 600, width: "100%" }}>
                  <Text size="sm" fw={500} mb={4} align="center">
                    Hangulat
                  </Text>
                  <Tabs value={discoverMood} onChange={(val) => { setDiscoverMood(val) }} keepMounted={false} color={dark ? "#483d8b" : "#FFC56E"}
                    styles={{ list: { display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 4, padding: 4, borderRadius: 12, backgroundColor: dark ? "#171429" : "#FFF8E7", border: `2px solid ${dark ? "#483d8b" : "#FFD966"}`},
                      tab: { borderRadius: 10, fontSize: "0.85rem", fontWeight: 600, padding: "10px 12px", color: dark ? "#FFFFFF" : "#0C1A2A", backgroundColor: "transparent", display: "flex", flexDirection: "column", alignItems: "center", gap: 4, transition: "all 0.15s ease", "&[data-active]": { backgroundColor: dark ? "#483d8b" : "#FFC56E", color: "#FFFFFF", boxShadow: dark ? "0 0 8px rgba(72,61,139,0.6)" : "0 0 8px rgba(255,215,102,0.6)", transform: "translateY(-2px)" }}}}>
                    <Tabs.List>
                      <Tabs.Tab value="any">
                        <span style={{ fontSize: "1.3rem" }}>🎲</span>
                        Mindegy
                      </Tabs.Tab>
                      <Tabs.Tab value="Melancholy">
                        <span style={{ fontSize: "1.3rem" }}>😢</span>
                        Szomorú
                      </Tabs.Tab>
                      <Tabs.Tab value="Cool">
                        <span style={{ fontSize: "1.3rem" }}>😄</span>
                        Vidám
                      </Tabs.Tab>
                      <Tabs.Tab value="Energizing">
                        <span style={{ fontSize: "1.3rem" }}>⚡</span>
                        Energizáló
                      </Tabs.Tab>
                      <Tabs.Tab value="Peaceful">
                        <span style={{ fontSize: "1.3rem" }}>🌙</span>
                        Nyugodt
                      </Tabs.Tab>
                    </Tabs.List>
                  </Tabs>
                </div>
                <div style={{ gridColumn: "1 / 3", justifySelf: "center", maxWidth: 550, width: "100%"}}>
                  <Text size="sm" fw={500} mb={4} align="center">
                    Kiadás ideje
                  </Text>
                  <SegmentedControl radius="md" fullWidth styles={{ root: { border: `2px solid ${dark ? "#483d8b" : "#FFD966"}`, padding: 2, borderRadius: 10, backgroundColor: dark ? "#171429" : "#FFF8E7" },
                  indicator: { backgroundColor: dark ? "#483d8b" : "#FFC56E", borderRadius: 8 }, label: { color: dark ? "#FFFFFF" : "#0C1A2A", fontWeight: 600, fontSize: "1rem" }, control: { transition: "all 0.2s ease" }}} value={releaseRange} onChange={setReleaseRange} data={[ { label: "Bármikor", value: "any" }, { label: "legújabbak", value: "new" }, { label: "2010-es évek", value: "2010s" }, { label: "2000-es évek", value: "2000s" }, { label: "Régebbiek", value: "old" }]}/>
                </div>
              </div>
              {!loadingDiscover && (
              <div style={{ marginTop: 18, display: "flex", justifyContent: "center" }}>
                <Button onClick={handleDiscoverSearch} size="md" radius="md" style={{ backgroundColor: dark ? "#7A4CFF" : "#FFD966", color: dark ? "#FFFFFF" : "#0C1A2A", minWidth: 180 }}>
                  Felfedezés indítása
                </Button> 
              </div>
              )}
              {loadingDiscover && (
                <div style={{ marginTop: 24, width: "100%", textAlign: "center" }}>
                  <div style={{marginBottom: 14}}>Szürés kiértékelése folyamatban</div>
                  <Progress value={progress} style={{ width: "70%", margin: "0 auto", height: 8, borderRadius: 6, backgroundColor: dark ? "#2A2550" : "#FFEFB3", }} color={dark ? "#7A4CFF" : "#FFD966"}/>
                  <div style={{ marginTop: 8, fontWeight: 600, fontSize: "0.95rem", color: dark ? "#CBB7FF" : "#6B5500", }}>{progress}%</div>
                </div>
              )}
            </div>

            {!loadingDiscover && discoverTracks.length > 0 && (
              <div>
                {(() => {
                  const track = discoverTracks[index];
                  if (!track) return null;
                  return (
                    <>
                      <div style={{ gridColumn: "1 / -1", marginTop: 20 }}>
                        <h2 style={{ marginBottom: 16, textAlign: "Center" }}>Talált Zenék:</h2>
                        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", flexDirection: "column" }}>
                          <div style={{ minWidth: 800, width: "100%", overflowX: "auto", background: dark ? "rgba(72, 61, 139, 0.3)" : "rgba(255, 217, 102, 0.3)", border: dark ? "3px solid #483d8b" : "3px solid #FFD966", borderRadius: 14 }}>
                            <table style={{ width: "100%", borderCollapse: "collapse" }}>
                              <thead style={{ background: dark ? "rgba(255, 255, 255, 0.1)" : "rgba(0,0,0,0.05)" }}>
                                <tr>
                                  <th style={{ textAlign: "center", padding: "12px 4px 12px 58px", fontWeight: 800 }}></th>
                                  <th style={{ textAlign: "center", padding: "12px 4px 12px 58px", fontWeight: 800 }}>Cím</th>
                                  <th style={{ textAlign: "center", padding: "12px 4px 12px 58px", fontWeight: 800 }}>Lejátszás</th>
                                </tr>
                              </thead>
                              <tbody>
                                {discoverTracks.map((t) => (
                                  <tr style={{ border: dark ? "1px solid #483d8b" : "1px solid #FFD966"}}>
                                    <td style={{ verticalAlign: "middle", padding: "12px", cursor: "pointer", textAlign: "center" }}><img src={t.image} alt="Borítókép" width={70} height={70} style={{ borderRadius: 4, verticalAlign: "middle" }}/></td>
                                    <td style={{ verticalAlign: "middle", textAlign: "left", fontSize: "1.2rem", cursor: "pointer" }} onClick={() => goToMusic(t.name, t.artists?.[0] || "")} title="Részletek a zenéről">
                                      <div style={{ fontWeight: 500 }}>
                                        {t.name}
                                      </div>
                                      <div style={{ fontSize: "0.9rem", opacity: 0.6, marginTop: 4, color: dark ? "#ccc" : "#555"}}>
                                        {t.artists?.[0]}
                                      </div>
                                    </td>
                                    <td style={{ verticalAlign: "middle", padding: "12px 12px 12px 58px", cursor: "pointer", textAlign: "center" }}>
                                      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 15}}>
                                        <img src="/icons/youtube_logo.png" alt="YouTube" width={40} height={40} style={{ cursor: "pointer" }}
                                          onClick={async () => {
                                            try {
                                              const query = `${(t.artists || []).join(" ")} ${t.name}`;
                                              const res = await fetch(`http://127.0.0.1:5000/api/music/youtube?q=${encodeURIComponent(query)}`);
                                              const data = await res.json();
                                              if (data.video_url) window.open(data.video_url, "_blank");
                                              else alert("Nem található konkrét YouTube videó ehhez a zenéhez.");}
                                            catch (err) {
                                              alert("Hiba történt a YouTube keresés során.");
                                              console.error(err);
                                            }}}/>
                                        <img src="/icons/spotify_logo.png" alt="Spotify" width={40} height={40} style={{ cursor: "pointer" }} onClick={async () => {
                                          try {
                                            const query = `${(t.artists || []).join(" ")} ${t.name}`;
                                            const res = await fetch(`http://127.0.0.1:5000/api/music/spotify?q=${encodeURIComponent(query)}`);
                                            const data = await res.json();
                                            if (data.track_url) window.open(data.track_url, "_blank");
                                            else alert("Nem található a Spotify-on ez a zene.");}
                                          catch (err) {
                                            alert("Hiba történt a Spotify keresés során.");
                                            console.error(err);
                                          }}}/>
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        )}
        {mode === "lyrics" && !loading && currentSong && (
          <div style={{ marginTop: 32, display: "flex", justifyContent: "center", alignItems: "center", flexDirection: "column" }}>
            <div
              style={{ width: "min(700px, 95%)", display: "flex", flexDirection: "column", alignItems: "center", gap: 24, padding: 24, borderRadius: 16, border: "1px solid rgba(0,0,0,0.06)", background: dark ? "rgba(255,255,255,0.04)" : "#FFF8E7", backdropFilter: "blur(6px)", boxShadow: dark ? "0 6px 24px rgba(0,0,0,0.35)" : "0 8px 24px rgba(12,26,42,0.08)" }}>
              <div style={{ flex: "0 0 280px", textAlign: "center" }}>
                {currentSong.cover && (
                  <img src={currentSong.cover} alt="Borítókép" style={{ width: 260, maxWidth: "100%", borderRadius: 12, marginBottom: 14,}}/>
                )}

                <h2 style={{ fontSize: "1.6rem", margin: "6px 0 4px 0" }}>
                  {currentSong.title}
                </h2>
              </div>

              <div style={{ flex: "1 1 420px", minWidth: 280 }}>
                {(() => {
                  const featured = Array.isArray(currentSong.featured_artists) ? currentSong.featured_artists.map((a) => (typeof a === "string" ? a : a?.name)).filter(Boolean): [];
                  const geniusUrl = currentSong.lyrics_url?.startsWith("http") ? currentSong.lyrics_url : `https://genius.com${currentSong.lyrics_url || ""}`;
                  const line = (label, value, extra = null) => (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", border: dark ? "1px solid #483d8b" : "1px solid #FFD966", textAlign: "center"}}>
                      <div style={{ width: 160, minWidth: 140, fontWeight: 600, opacity: 0.85, textAlign: "left"}}>
                        {label}
                      </div>
                      <div style={{ flex: 1, textAlign: "center" }}>{value || "—"}</div>
                      {extra}
                    </div>
                  );

                  return (
                    <div style={{ borderRadius: 12, overflow: "hidden", border: dark ? "3px solid #483d8b" : "3px solid #FFD966" }}>
                      {line("Előadó:",
                        <span style={{ textDecoration: "underline", cursor: "pointer" }} onClick={() => goToArtist(currentSong.artist)} title="Részletek az előadóról">
                          {currentSong.artist}
                        </span>
                      )}

                      {line("Kiadás dátuma:", currentSong.release_date || "Ismeretlen")}

                      {line("Megtekintések:", (currentSong.views ?? 0).toLocaleString("hu-HU"))}

                      {line("Közreműködők:", featured.length ? (
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                            {featured.map((name) => (
                              <span key={name} style={{ padding: "4px 8px", borderRadius: 999, fontSize: 12, border: "1px solid rgba(0,0,0,0.12)", background: dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)" }}>
                                {name}
                              </span>
                            ))}
                          </div>
                        ) : ("Nincs közreműködő")
                      )}

                      {line("Dalszöveg:", geniusUrl ? (
                          <a href={geniusUrl} target="_blank" rel="noreferrer" style={{ textDecoration: "underline" }}>
                            Megnyitás
                          </a>) : ("—")
                      )}
                      {line( "Népszerűség:", currentSong.popularity ? "🔥 Jelenleg népszerű" : "Jelenleg nem népszerű")}
                      <div style={{ justifyContent: "center" }}>
                        {line( "Platformok:", 
                        <div style={{ display: "flex", gap: 16, justifyContent: "center" }}>
                          <img src="/icons/youtube_logo.png" alt="YouTube" width={40} height={40} style={{ cursor: "pointer" }} onClick={async () => {
                            try {
                              const query = `${currentSong.artist} ${currentSong.title}`;
                              const res = await fetch(`http://127.0.0.1:5000/api/music/youtube?q=${encodeURIComponent(query)}`);
                              const data = await res.json();
                              if (data.video_url) window.open(data.video_url, "_blank");
                              else alert("Nem található konkrét YouTube videó ehhez a zenéhez.");}
                            catch (err) {
                              alert("Hiba történt a YouTube keresés során.");
                              console.error(err);
                            }}}/>
                          <img src="/icons/spotify_logo.png" alt="Spotify" width={40} height={40} style={{ cursor: "pointer" }} onClick={async () => {
                            try {
                              const query = `${currentSong.artist} ${currentSong.title}`;
                              const res = await fetch(`http://127.0.0.1:5000/api/music/spotify?q=${encodeURIComponent(query)}`);
                              const data = await res.json();
                              if (data.track_url) window.open(data.track_url, "_blank");
                              else alert("Nem található a Spotify-on ez a zene.");}
                            catch (err) {
                              alert("Hiba történt a Spotify keresés során.");
                              console.error(err);
                            }}}/>
                        </div>
                        )}
                      </div>
                    </div>
                  );
                })()}
                {songs.length > 1 && (
                  <div style={{ display: "flex", justifyContent: "center",alignItems: "center", gap: 20, marginTop: 18,}}>
                    <Button onClick={handlePrev} disabled={index === 0} size="md" radius="md" style={{ backgroundColor: dark ? "#483d8b" : "#FFD966", color: dark ? "#FFFFFF" : "#0C1A2A", minWidth: 120 }}>
                      Előző
                    </Button>
                    <div style={{ fontWeight: 600, fontSize: "1rem", width: 50, textAlign: "center" }}>
                      {index + 1} / {songs.length}
                    </div>
                    <Button onClick={handleNext} disabled={index >= songs.length - 1} size="md" radius="md"style={{ backgroundColor: dark ? "#483d8b" : "#FFD966", color: dark ? "#FFFFFF" : "#0C1A2A", minWidth: 120}}>
                      Következő
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      {mode === "artist" && !loading && artist && (
        <div style={{ marginTop: 40, display: "flex", flexDirection: "column", gap: 32 }}>
          <section style={{ display: "grid", gridTemplateColumns: "280px 1fr", alignItems: "flex-start", gap: 30 }}>
            <div style={{ textAlign: "center" }}>
              {artist.image && (
                <img src={artist.image} alt={artist.name} style={{ width: 250, height: 250, objectFit: "cover", borderRadius: 16, marginBottom: 12, }}/>
              )}
              <h2 style={{ margin: 0 }}>{artist.name}</h2>
              <div>
                {artist.alternate_names && artist.alternate_names.length > 0 && (
                  <div style={{ fontStyle: "italic", opacity: 0.5, marginTop: 4 }}>
                    {artist.alternate_names.join(", ")}
              </div>)}
              </div>
            </div>
            <div>
              <p style={{ fontFamily: "Montserrat, sans-serif", fontStyle: "italic", fontSize: "0.95rem", opacity: 0.9, lineHeight: 1.6, marginTop: 0 }}>
                {artist.description || "Ehhez az előadóhoz nincs rövid leírás."}
              </p>
            </div>
            </section>
            <section>
              <div style={{ gridColumn: "1 / -1" }}>
                <h3 style={{ textAlign: "Center" }}>Egyéb adatok:</h3>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <div style={{ maxWidth: 800, width: "100%", overflowX: "auto", background: dark ? "rgba(72, 61, 139, 0.3)" : "rgba(255, 217, 102, 0.3)", border: dark ? "3px solid #483d8b" : "3px solid #FFD966", borderRadius: 14 }}>
                    {line("Stílusok:",<span>{artist.genres && artist.genres.length > 0 ? artist.genres.join(", ") : "Ismeretlen"}</span>)}
                    {line("Népszerűségi értékelése(0-100):",<span>{artist.spotify_popularity || "Ismeretlen"}</span>)}
                    {line("Követők száma:",<span>{artist.spotify_followers.toLocaleString("hu-HU") || "Ismeretlen"}</span>)}
                  </div>
                </div>
              </div>
            </section>
            {artist.top_songs && artist.top_songs.length > 0 && (
              <section>
              <div style={{ gridColumn: "1 / -1", marginTop: 20 }}>
                <h3 style={{ marginBottom: 16, textAlign: "Center" }}>Ismertebb dalok:</h3>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <div style={{ maxWidth: 800, width: "100%", overflowX: "auto", background: "rgba(0,0,0,0)", border: dark ? "3px solid #483d8b" : "3px solid #FFD966", borderRadius: 14 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead style={{ background: dark ? "rgba(72, 61, 139, 0.3)" : "rgba(255, 217, 102, 0.3)" }}>
                        <tr>
                          <th style={{ textAlign: "left", padding: "12px 4px 12px 58px", fontWeight: 700 }}></th>
                          <th style={{ textAlign: "center", padding: "12px 4px 12px", fontWeight: 700 }}>Cím</th>
                          <th style={{ textAlign: "center", padding: "12px 4px", fontWeight: 700 }}>Megjelenés</th>
                          <th style={{ textAlign: "center", padding: "12px 4px", fontWeight: 700 }}>Megtekintések<br></br>(Genius)</th>
                          <th style={{ textAlign: "center", padding: "12px 12px 12px 4px", fontWeight: 700 }}>Lejátszás</th>
                        </tr>
                      </thead>
                      <tbody>
                        {artist.top_songs.map((s) => {
                          const year = s.release_date ? s.release_date.slice(-4) : "-";
                          const views = typeof s.views === "number" ? s.views.toLocaleString("hu-HU") : "-";
                          return (
                            <tr key={s.id || s.title} style={{ background: dark ? "rgba(72, 61, 139, 0.3)" : "rgba(255, 217, 102, 0.3)", border: dark ? "1px solid #483d8b" : "1px solid #FFD966" }}>
                              <td style={{ verticalAlign: "middle", padding: "12px", cursor: "pointer", textAlign: "center" }}>{s.image && ( <img src={s.image} alt={s.title} style={{ width: 42, height: 42, borderRadius: 8, objectFit: "cover" }}/>)}</td>
                              <td style={{ textAlign: "left", cursor: "pointer"}} onClick={() => goToMusic(s.title)} title="Részletek a zenéről">{s.title}</td>
                              <td style={{ textAlign: "center" }}>{year}</td>
                              <td style={{ textAlign: "center" }}>{views}</td>
                              <td style={{ textAlign: "center" }}>
                                <img src="/icons/youtube_logo.png" alt="YouTube" width={26} style={{ cursor: "pointer", marginRight: 8, verticalAlign: "middle" }} onClick={async () => {
                                    try {
                                      const query = `${artist.name} ${s.title}`;
                                      const res = await fetch(`http://127.0.0.1:5000/api/music/youtube?q=${encodeURIComponent(query)}`);
                                      const data = await res.json();
                                      if (data.video_url) {
                                        window.open(data.video_url, "_blank");
                                      } else {
                                        alert("Nem található YouTube videó ehhez a zenéhez.");
                                      }}
                                    catch (err) {
                                      console.error(err);
                                      alert("Hiba történt a YouTube keresés során.");
                                    }}}/>
                                <img src="/icons/spotify_logo.png" alt="Spotify" width={26} style={{ cursor: "pointer", verticalAlign: "middle" }} onClick={async () => {
                                    try {
                                      const query = `${artist.name} ${s.title}`;
                                      const res = await fetch(`http://127.0.0.1:5000/api/music/spotify?q=${encodeURIComponent(query)}`);
                                      const data = await res.json();
                                      if (data.track_url) {
                                        window.open(data.track_url, "_blank");
                                      } else {
                                        alert("Nem található a Spotify-on ez a zene.");
                                      }}
                                    catch (err) {
                                      console.error(err);
                                      alert("Hiba történt a Spotify keresés során.");
                                    }}}/>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
              </section>
            )}
          </div>
      )}

      {error && (
        <p style={{ marginTop: 24, textAlign: "center", color: "#d9534f", fontWeight: 600 }}>{error}</p>
      )}
        <Box style={{ maxWidth: 800, textAlign: "center", marginTop: 60, marginBottom: 10, color: dark ? "#D1D5DB" : "#333" }}>
          {mode === "lyrics" ? (
          <>
          <h2 style={{ fontSize: "2rem", marginBottom: 12 }}>Hogyan működik?</h2>
          <p style={{ fontSize: "1.2rem", lineHeight: 1.6 }}>
            Van egy dal, ami nem megy ki a fejedből?
            Talán csak a szöveg egy részére emlékszel, például: „Egy dalt keresek, ami így szól…”
            Ez az eszköz segít megtalálni azokat a dalokat, amelyek tartalmazzák az általad felidézett dalszöveget!
          </p>
          <p style={{ fontSize: "1.2rem", lineHeight: 1.6 }}>
            Írd be a dalszöveg egy részét, és az oldal megpróbálja felismerni, melyik dalról van szó.  
            Nem kell tudnod az előadót, és a szöveg sem kell pontos legyen.
          </p>
          <p style={{ fontSize: "1.2rem", marginTop: 8, lineHeight: 1.6 }}>
            Ezután kiválaszthatod a legjobb egyezést.
            A találatoknál megjelenik a borítókép, az előadó a cím és sok más információ.
            Lehetőséget kapsz arra is, hogy meghallgasd a dalt YouTube-on vagy Spotify-on.  
          </p>
          </>
          ) : mode === "artist" ? (
          <>
          <h2 style={{ fontSize: "2rem", marginBottom: 12 }}>Hogyan működik?</h2>
          <p style={{ fontSize: "1.2rem", lineHeight: 1.6 }}>
            Szeretnél többet megtudni kedvenc zeneszerzőidről vagy előadóidról?
            Ez az eszköz segít neked abban, hogy gyorsan és egyszerűen információkat találj róluk!
          </p>
          <p style={{ fontSize: "1.2rem", lineHeight: 1.6 }}>
            Csak írd be a zeneszerző vagy előadó nevét a keresőmezőbe, és az oldal megkeresi a releváns adatokat.
            Elolvashatod a rövid életrajzukat, megismerheted a népszerűbb dalaikat és akár egy képet is láthatsz róluk.
          </p>
          </>
          ) : (
          <>
          <h2 style={{ fontSize: "2rem", marginBottom: 12 }}>Hogyan működik?</h2>
          <p style={{ fontSize: "1.2rem", lineHeight: 1.6 }}>
            Szeretnél új zenéket felfedezni a kedvenc műfajaidban vagy hangulatodhoz illően?
            Ez az eszköz segít neked abban, hogy személyre szabott zenei ajánlásokat kapj!
          </p>
          <p style={{ fontSize: "1.2rem", lineHeight: 1.6 }}>
            Válaszd ki a kedvenc műfajaidat, állítsd be a népszerűségi szintet, hangulatot, energiát és táncolhatóságot.
            Az oldal ezek alapján keres neked új zenéket, amelyeket még nem ismersz.
          </p>
          <p style={{ fontSize: "1.2rem", marginTop: 8, lineHeight: 1.6 }}>
            A találatok között megjelenik a borítókép, a cím és lehetőséged van meghallgatni a dalokat YouTube-on vagy Spotify-on.
          </p>
          </>
          ) }
        </Box>
      </Card>
    </div>
  );
}

export { Search };