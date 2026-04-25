import React, { useState, useRef, useEffect, useMemo } from "react";
import { Button, Loader, Text, Card, Progress, Accordion, RingProgress, Group, Stack, Tooltip, ActionIcon } from "@mantine/core";
import { useMantineColorScheme } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { Link } from "react-router-dom";
import WaveformPlayer from "@arraypress/waveform-player";
import "@arraypress/waveform-player/dist/waveform-player.css";
import DonutChart from "../components/DonutChart.jsx";
import SectionCard from "../components/SectionCard.jsx";
import DualBar from "../components/DualBar.jsx";
import { IconInfoCircle } from "@tabler/icons-react";

export default function MusicAnalyzer() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === "dark";

  const InfoHeader = ({ title, desc }) => (
    <Group gap={6} align="center" wrap="nowrap">
      <h3 style={{ margin: 0 }}>{title}</h3>
      {desc && (
        <Tooltip label={desc} withArrow multiline maw={260}>
          <ActionIcon variant="subtle" color={dark ? "yellow" : "violet"} size="sm" aria-label={desc}>
            <IconInfoCircle size={16} />
          </ActionIcon>
        </Tooltip>
      )}
    </Group>
  );

  const pct = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? Math.max(0, Math.min(100, n * 100)) : 0;
  };

  // Közös kördiagram-paletta (témához igazodó)
  const donutPalette = useMemo(() => {
    const light = [
      "#5B8FF9",
      "#61DDAA",
      "#65789B",
      "#F6BD16",
      "#7262FD",
      "#78D3F8",
      "#9661BC",
      "#F6903D",
    ];
    const darkP = [
      "#8AB4F8",
      "#34D399",
      "#9AA5B1",
      "#FBBF24",
      "#A78BFA",
      "#67E8F9",
      "#C084FC",
      "#F59E0B",
    ];
    return dark ? darkP : light;
  }, [dark]);

  // Műfaj jelöltek + színek
  const genreCandidates = useMemo(() => {
    if (!Array.isArray(result?.genre_model_candidates)) return [];
    return result.genre_model_candidates.slice(0, 6).map((c) => ({
      label: c.label,
      value: Math.max(0, Number(c.score) || 0),
    }));
  }, [result?.genre_model_candidates]);

  const genreColors = useMemo(() => genreCandidates.map((_, i) => donutPalette[i % donutPalette.length]), [genreCandidates, donutPalette]);

  // MIREX jelöltek + színek
  const mirexCandidates = useMemo(() => {
    if (!Array.isArray(result?.mood_mirex_candidates)) return [];
    return result.mood_mirex_candidates.slice(0, 6).map((c) => ({
      label: c.label,
      value: Math.max(0, Number(c.score) || 0),
    }));
  }, [result?.mood_mirex_candidates]);

  const mirexColors = useMemo(() => mirexCandidates.map((_, i) => donutPalette[i % donutPalette.length]), [mirexCandidates, donutPalette]);

  const brightDarkCandidates = useMemo(() => {
    if (!Array.isArray(result?.bright_dark_candidates)) return [];
    return result.bright_dark_candidates.map((c) => ({
      label: c.label,
      value: Math.max(0, Number(c.score) || 0),
    }));
  }, [result?.bright_dark_candidates]);

  const voiceInstCandidates = useMemo(() => {
    if (!Array.isArray(result?.voice_instrumental_candidates)) return [];
    return result.voice_instrumental_candidates.map((c) => ({
      label: c.label,
      value: Math.max(0, Number(c.score) || 0),
    }));
  }, [result?.voice_instrumental_candidates]);

  const moodAcousticCandidates = useMemo(() => {
    if (!Array.isArray(result?.mood_acoustic_candidates)) return [];
    return result.mood_acoustic_candidates.map((c) => ({
      label: c.label,
      value: Math.max(0, Number(c.score) || 0),
    }));
  }, [result?.mood_acoustic_candidates]);

  const handleAnalyze = async () => {
    if (!file) return alert("Válassz egy MP3 fájlt!");
    const formData = new FormData();
    formData.append("file", file);
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("http://127.0.0.1:5000/api/music/analyze", { method: "POST", body: formData });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Hiba történt az elemzés során");
      }
      const data = await res.json();
      console.log("[music_analyzer] analysis result", data);
      setResult(data);
    } catch (e) {
      console.error(e);
      alert("Nem sikerült elemezni a fájlt.");
    } finally {
      setLoading(false);
    }
  };

  // Húzd és ejtsd események a Dropzone komponensen keresztül

  const containerRef = useRef(null);

  const playerRef = useRef(null);

  useEffect(() => {
    if (!result?.path || !containerRef.current) return;
    const el = containerRef.current;
    let playerInstance = null;
    try {
      playerInstance = new WaveformPlayer(el);
      playerRef.current = playerInstance;
    } catch (e) {
      console.error("[WaveformPlayer] init error:", e);
    }

    const handleResize = () => {
      if (!playerRef.current || !el || !el.isConnected) return;
      try {
        playerRef.current.resize?.();
      } catch {}
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      try {
        playerInstance?.destroy?.();
      } catch {}
      playerRef.current = null;
    };
  }, [result?.path]);
  
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "calc(100vh - 100px)", marginTop: 15 }}>
      <Card shadow="xl" padding="xl" radius="lg" withBorder style={{ width: "100%", maxWidth: 800, backgroundColor: dark ? "#0C1A2A" : "#FFF8E7", color: dark ? "#FFFFFF" : "#0C1A2A", borderColor: dark ? "#483d8b" : "#FFD966" }}>
        <h1 style={{ textAlign: "center", marginBottom: 28, fontSize: "3rem", fontWeight: 700 }}>Zeneelemző</h1>
        <Text size="lg" style={{ textAlign: "center", opacity: 0.8, marginBottom: 16 }}>Tölts fel egy MP3 fájlt, hogy elemezzük a zenei jellemzőit.</Text>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>
        </div>

        <Dropzone
          onDrop={(files) => {
            const f = files?.[0];
            if (f) setFile(f);
          }}
          onReject={() => alert("Csak audio fájlokat fogadunk el.")}
          accept={{
            "audio/*": [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"],
          }}
          multiple={false}
          styles={{
            root: {
              marginTop: 20,
              padding: 24,
              border: `2px solid  ${dark ? "#a78bfa" : "#FFD966"}`,
              borderRadius: 12,
              backgroundColor: dark ? "#0F1B2A" : "#FFFDF5",
              cursor: "pointer",
              textAlign: "center",
              transition: "background-color 0.2s ease, border-color 0.2s ease",
            },
          }}
        >
          <div style={{ textAlign: "center" }}>
            <Text size="sm" style={{ opacity: 0.8 }}>
              Húzd ide az audio fájlt, vagy <u>kattints</u> a kiválasztáshoz.
            </Text>
            {file && (
              <Text size="sm" style={{ marginTop: 6 }}>
                Kiválasztva: {file.name}
              </Text>
            )}
          </div>
        </Dropzone>

        <div style={{ textAlign: "center", marginTop: 32, display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <Button onClick={handleAnalyze} disabled={loading || !file} size="md" radius="md" style={{ backgroundColor: dark ? "#483d8b" : "#FFD966", color: dark ? "#FFFFFF" : "#0C1A2A", width: 200, height: 45 }}>
            {loading ? <Loader size="sm" color={dark ? "violet" : "yellow"} /> : "Elemzés indítása"}
          </Button>
          {result && (
            <Button
              component={Link}
              to="/music-recommender"
              state={{ features: result, query: result.artist && result.title ? `${result.artist} ${result.title}` : "" }}
              variant="outline"
              color={dark ? "violet" : "yellow"}
              size="md"
              radius="md"
            >
              Ajánló ehhez
            </Button>
          )}
        </div>

        {result && (
          <div style={{ marginTop: 20 }}>
            <h2>Elemzett adatok</h2>
            <Stack gap={16}>
              <SectionCard>
                <Group justify="space-between" align="center">
                                    {result.cover && (
                    <div
                      style={{
                        width: 120,
                        height: 120,
                        borderRadius: 12,
                        overflow: "hidden",
                        flexShrink: 0,
                        background: dark ? "rgba(255,255,255,0.06)" : "#f3f3f3",
                      }}
                    >
                      <img
                        src={`http://127.0.0.1:5000/api/music/uploads/${result.cover}`}
                        alt={result.title || "Borító"}
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                    </div>
                  )}
                  <div>
                    <Text fw={700} size="lg">Alapadatok</Text>
                    <Text c="dimmed" size="sm">{result.title} - {result.artist}</Text>
                    <Text c="dimmed" size="sm">Hossz: {Number(result.duration).toFixed(1)} mp | Kulcs (Camelot): {result.camelot}</Text>
                  </div>
                  <div style={{ minWidth: 140, textAlign: "center" }}>
                    <RingProgress size={120} thickness={12} sections={[{ value: Math.min(100, Math.max(0, (Number(result.bpm) || 0) / 2)), color: dark ? "violet.5" : "violet.6" }]} label={<Text size="sm" ta="center"><strong>BPM</strong><br/>{result.bpm || "?"}</Text>} />
                  </div>
                </Group>
              </SectionCard>
              {/* Rejtve: tempó-bizalom, átlagos összeg, ReplayGain és lokális heurisztikák */}
            </Stack>

            {(result.genre_model_name || result.genre_model || (Array.isArray(result.genre_model_candidates) && result.genre_model_candidates.length > 0)) && (
              <SectionCard>
                <InfoHeader
                  title="Modell szerinti műfaj"
                  desc="A tanított műfajmodell fő/makró műfaj becslése, százalékos valószínűségekkel."
                />
                <Text><strong>Fő műfaj:</strong> {result.genre_model || "ismeretlen"}</Text>
                {result.genre_model_macro && (<Text><strong>Makró műfaj:</strong> {result.genre_model_macro}</Text>)}
                {Array.isArray(result.genre_model_candidates) && result.genre_model_candidates.length > 0 && (
                  <div style={{ marginTop: 8, display: 'flex', gap: 16, alignItems: 'center' }}>
                    <DonutChart
                      size={160}
                      thickness={25}
                      data={genreCandidates}
                      colors={genreColors}
                    />
                    <div style={{ flex: 1 }}>
                      {genreCandidates.map((c, idx) => (
                        <div key={c.label} style={{ marginBottom: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', backgroundColor: genreColors[idx] }} />
                              <Text size="sm" fw={600}>{c.label}</Text>
                            </div>
                            <Text size="sm" color="dimmed">{(c.value * 100).toFixed(1)}%</Text>
                          </div>
                          <Progress value={pct(c.value)} radius="sm" styles={{ section: { backgroundColor: genreColors[idx] } }} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </SectionCard>
            )}

            {(result.approachability_model_name || result.approachability_top || result.approachability_score) && (
              <SectionCard>
                <InfoHeader
                  title="Megközelíthetőség"
                  desc="Mennyire közérthető, mainstream jellegű a zene. Magasabb érték: könnyen befogadható; alacsonyabb: réteg/experimentális."
                />
                {typeof result.approachability_score === 'number' && (
                  <div style={{ marginTop: 8 }}>
                    <Text><strong>Érték:</strong> {(Number(result.approachability_score) * 100).toFixed(1)}%</Text>
                    <Progress value={pct(result.approachability_score)} radius="sm" />
                  </div>
                )}
                {result.approachability_top && (
                  <Text style={{ marginTop: 8 }}><strong></strong></Text>
                )}
                {Array.isArray(result.approachability_candidates) && result.approachability_candidates.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {result.approachability_candidates.slice(0, 5).map((c) => (
                      <div key={c.label} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <Text size="sm" fw={600}>{c.label}</Text>
                          <Text size="sm" color="dimmed">{(Number(c.score) * 100).toFixed(1)}%</Text>
                        </div>
                        <Progress value={pct(c.score)} radius="sm" />
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {(result.danceability_model_name || result.danceability_score || result.danceability_top) && (
              <SectionCard>
                <InfoHeader
                  title="Táncolhatóság"
                  desc="Mennyire alkalmas táncra: ritmus, beat stabilitás, groove. Magasabb érték: könnyen táncolható."
                />
                {typeof result.danceability_score === 'number' && (
                  <div style={{ marginTop: 8 }}>
                    <Text><strong>Érték:</strong> {(Number(result.danceability_score) * 100).toFixed(1)}%</Text>
                    <Progress value={pct(result.danceability_score)} radius="sm" />
                  </div>
                )}
                {result.danceability_top && (
                  <Text style={{ marginTop: 8 }}><strong></strong></Text>
                )}
                {Array.isArray(result.danceability_candidates) && result.danceability_candidates.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {result.danceability_candidates.slice(0, 5).map((c) => (
                      <div key={c.label} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <Text size="sm" fw={600}>{c.label}</Text>
                          <Text size="sm" color="dimmed">{(Number(c.score) * 100).toFixed(1)}%</Text>
                        </div>
                        <Progress value={pct(c.score)} radius="sm" />
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {(result.engagement_model_name || result.engagement_score || result.engagement_top) && (
              <SectionCard>
                <InfoHeader
                  title="Elköteleződés"
                  desc="Mennyire igényel aktív figyelmet a hallgatótól. Magasabb érték: 'lean forward' élmény; alacsonyabb: háttérzene."
                />
                {typeof result.engagement_score === 'number' && (
                  <div style={{ marginTop: 8 }}>
                    <Text><strong>Érték:</strong> {(Number(result.engagement_score) * 100).toFixed(1)}%</Text>
                    <Progress value={pct(result.engagement_score)} radius="sm" />
                  </div>
                )}
                {result.engagement_top && (
                  <Text style={{ marginTop: 8 }}><strong></strong></Text>
                )}
                {Array.isArray(result.engagement_candidates) && result.engagement_candidates.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {result.engagement_candidates.slice(0, 5).map((c) => (
                      <div key={c.label} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <Text size="sm" fw={600}>{c.label}</Text>
                          <Text size="sm" color="dimmed">{(Number(c.score) * 100).toFixed(1)}%</Text>
                        </div>
                        <Progress value={pct(c.score)} radius="sm" />
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {(result.bright_dark_model_name || result.bright_dark_top) && (
              <SectionCard>
                <InfoHeader
                  title="Spektrális szín (bright/dark)"
                  desc="Világos vs. sötét hangzás: magas frekvenciák dominanciája vs. mélyebb, sötétebb spektrum."
                />
                {result.bright_dark_top && (
                  <Text style={{ marginTop: 8 }}><strong></strong></Text>
                )}
                {brightDarkCandidates.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {brightDarkCandidates.slice(0, 4).map((c) => (
                      <div key={c.label} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <Text size="sm" fw={600}>{c.label}</Text>
                          <Text size="sm" color="dimmed">{(c.value * 100).toFixed(1)}%</Text>
                        </div>
                        <Progress value={pct(c.value)} radius="sm" />
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {(result.voice_instrumental_model_name || result.voice_instrumental_top) && (
              <SectionCard>
                <InfoHeader
                  title="Vokál / Instrumentális"
                  desc="Mennyire ének-központú a felvétel a hangszeres tartalomhoz képest."
                />
                {result.voice_instrumental_top && (
                  <Text style={{ marginTop: 8 }}><strong></strong></Text>
                )}
                {voiceInstCandidates.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {voiceInstCandidates.slice(0, 4).map((c) => (
                      <div key={c.label} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <Text size="sm" fw={600}>{c.label}</Text>
                          <Text size="sm" color="dimmed">{(c.value * 100).toFixed(1)}%</Text>
                        </div>
                        <Progress value={pct(c.value)} radius="sm" />
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {(result.valence_arousal_model_name || typeof result.arousal === "number" || typeof result.valence === "number") && (
              <SectionCard>
                <InfoHeader
                  title="Érzelmi profil"
                  desc="Valencia (pozitív–negatív érzet) és arousal (nyugodt–intenzív aktiváltság) skálákon mért érzelmi helyzet."
                />
                <div style={{ marginTop: 8 }}>
                  <DualBar leftLabel="Arousal" leftValue={result.arousal} rightLabel="Valencia" rightValue={result.valence} />
                </div>
              </SectionCard>
            )}

            {(result.mood_acoustic_model_name || result.mood_acoustic_top) && (
              <SectionCard>
                <InfoHeader
                  title="Akusztikus jelleg"
                  desc="Az akusztikus textúra/mood becslése (pl. organikus, elektronikus, ambient, nyers), valószínűségi megoszlással."
                />
                {result.mood_acoustic_top && (
                  <Text style={{ marginTop: 8 }}><strong></strong></Text>
                )}
                {moodAcousticCandidates.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {moodAcousticCandidates.slice(0, 4).map((c) => (
                      <div key={c.label} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <Text size="sm" fw={600}>{c.label}</Text>
                          <Text size="sm" color="dimmed">{(c.value * 100).toFixed(1)}%</Text>
                        </div>
                        <Progress value={pct(c.value)} radius="sm" />
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            )}

            {(result.mood_mirex_model_name || result.mood_mirex_top) && (
              <SectionCard>
                <InfoHeader
                  title="Hangulat"
                  desc="MIREX-hangulatkategóriák (pl. vidám, lírai, energikus) szerinti becslés, valószínűségi megoszlással."
                />
                {result.mood_mirex_top && (
                  <Text style={{ marginTop: 8 }}><strong>Fő hangulat:</strong> {result.mood_mirex_top}</Text>
                )}
                {Array.isArray(result.mood_mirex_candidates) && result.mood_mirex_candidates.length > 0 && (
                  <div style={{ marginTop: 8, display: 'flex', gap: 16, alignItems: 'center' }}>
                    <DonutChart
                      size={160}
                      thickness={25}
                      data={mirexCandidates}
                      colors={mirexColors}
                    />
                    <div style={{ flex: 1 }}>
                      {mirexCandidates.map((c, idx) => (
                        <div key={c.label} style={{ marginBottom: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', backgroundColor: mirexColors[idx] }} />
                              <Text size="sm" fw={600}>{c.label}</Text>
                            </div>
                            <Text size="sm" color="dimmed">{(c.value * 100).toFixed(1)}%</Text>
                          </div>
                          <Progress value={pct(c.value)} radius="sm" styles={{ section: { backgroundColor: mirexColors[idx] } }} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </SectionCard>
            )}

            

            {result.path && (
              <div style={{ marginTop: "1rem" }}>
                <Text><strong>Lejátszás:</strong></Text>
                <Group align="flex-start" gap="md" wrap="nowrap" mt={6}>
                  <div style={{ flex: 1 }}>
                    <div
                      ref={containerRef}
                      data-waveform-player
                      data-url={`http://127.0.0.1:5000/api/music/uploads/${result.path}`}
                      data-title={result?.title || "Feltöltött fájl"}
                      data-subtitle={result?.artist || ""}
                      data-waveform-style="bars"
                      data-bar-width="4"
                      data-bar-spacing="1"
                      data-height="96"
                      data-samples="300"
                      data-show-playback-speed="true"
                      data-show-time="true"
                      data-show-volume="true"
                      style={{
                        width: "100%",
                        borderRadius: 12,
                        marginTop: 8,
                      }}
                    />
                    {/* YouTube + Spotify ikonok */}
                    <div
                      style={{
                        marginTop: 16,
                        display: "flex",
                        justifyContent: "center",
                        gap: 20,
                      }}
                    >
                      {/* YouTube ikon */}
                      <img
                        src="/icons/youtube_logo.png"
                        alt="YouTube"
                        width={36}
                        height={36}
                        style={{ cursor: "pointer" }}
                        onClick={async () => {
                          try {
                            const query = `${result.artist} ${result.title}`;
                            const res = await fetch(
                          `http://127.0.0.1:5000/api/music/youtube?q=${encodeURIComponent(
                            query
                          )}`
                        );
                        const data = await res.json();
                        if (data.video_url) {
                          window.open(data.video_url, "_blank");
                        } else {
                          alert("Nem található konkrét YouTube videó ehhez a zenéhez.");
                        }
                      } catch (error) {
                        alert("Hiba történt a YouTube keresés során.");
                        console.error(error);
                      }
                    }}
                  />

                      {/* Spotify ikon */}
                      <img
                        src="/icons/spotify_logo.png"
                        alt="Spotify"
                        width={36}
                        height={36}
                        style={{ cursor: "pointer" }}
                        onClick={async () => {
                          try {
                            const query = `${result.artist} ${result.title}`;
                            const res = await fetch(
                          `http://127.0.0.1:5000/api/music/spotify?q=${encodeURIComponent(
                            query
                          )}`
                        );
                        const data = await res.json();
                        if (data.track_url) {
                          window.open(data.track_url, "_blank");
                        } else {
                          alert("Nem található ez a zene a Spotify-on.");
                        }
                      } catch (error) {
                        alert("Hiba történt a Spotify keresés során.");
                        console.error(error);
                      }
                        }}
                      />
                    </div>
                  </div>
                </Group>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

export { MusicAnalyzer };
