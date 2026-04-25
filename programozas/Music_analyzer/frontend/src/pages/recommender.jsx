import React, { useEffect, useState } from "react";
import { Card, Text, Title, Group, Button, useMantineColorScheme, TextInput, Loader } from "@mantine/core";
import { Link, useLocation } from "react-router-dom";

const sampleTracks = [
  {
    title: "Chillwave Sunsets",
    artist: "Nova Collective",
    link: "https://example.com/chillwave",
    previewUrl: "",
    score: 0.92,
  },
  {
    title: "Acoustic Breeze",
    artist: "Jacob Rivers",
    link: "https://example.com/acoustic",
    previewUrl: "",
    score: 0.88,
  },
  {
    title: "Midnight Drive",
    artist: "Luminous",
    link: "https://example.com/midnight",
    previewUrl: "",
    score: 0.83,
  },
];

export default function Recommender() {
  const [query, setQuery] = useState("");
  const [tracks, setTracks] = useState(sampleTracks);
  const [seed, setSeed] = useState(null);
  const [loading, setLoading] = useState(false);
  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === "dark";
  const location = useLocation();

  const handleSearch = async (initialQuery, initialFeatures) => {
    const raw = initialQuery ?? query ?? "";
    const q = typeof raw === "string" ? raw.trim() : String(raw || "").trim();
    const feats = initialFeatures ?? location.state?.features;
    if (!q && !feats) return;
    setLoading(true);
    try {
      const payload = {
        query: q || undefined,
        features: feats,
      };

      const res = await fetch("http://127.0.0.1:5000/api/music/recommend-external", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.error) {
        alert(data.error);
        return;
      }
      setSeed(data.seed || null);
      const recs = Array.isArray(data.recommendations) && data.recommendations.length > 0 ? data.recommendations : sampleTracks;
      const mapped = recs.map((r) => ({
        title: r.title || "Ismeretlen cím",
        artist: r.artist || "Ismeretlen előadó",
        link: r.url || "",
        previewUrl: r.preview_url || "",
        thumbnail: r.thumbnail || (r.thumbnails && r.thumbnails[0]?.url) || "",
      }));
      setTracks(mapped);
    } catch (e) {
      console.error(e);
      alert("Nem sikerült ajánlást lekérni a helyi adatbázisból.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const incomingQuery = location.state?.query || "";
    const incomingFeatures = location.state?.features;
    if (incomingQuery || incomingFeatures) {
      if (incomingQuery) setQuery(incomingQuery);
      handleSearch(incomingQuery, incomingFeatures);
    }
  }, [location.state]);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "calc(100vh - 100px)", width: "100%" }}>
      <Card
        shadow="xl"
        padding="xl"
        radius="lg"
        withBorder
        style={{
          width: "100%",
          maxWidth: 920,
          backgroundColor: dark ? "rgba(12,26,42,0.85)" : "#FFF8E7",
          color: dark ? "#fff" : "#0C1A2A",
          borderColor: dark ? "#483d8b" : "#FFD966",
        }}
      >
        <Group justify="space-between" align="center" mb={12}>
          <div>
            <Title order={2} style={{ color: dark ? "#FFD966" : "#483d8b" }}>Zeneajánló</Title>
            <Text size="sm" c={dark ? "gray.2" : "gray.7"} mt={4}>Ajánlott zenék a saját adatbázisból, az elemzett jellemzők alapján</Text>
          </div>
          <Button component={Link} to="/music-analyzer" variant="light" color={dark ? "yellow" : "violet"} radius="md">Vissza az elemzőhöz</Button>
        </Group>

        <Group gap={8} mb={16} align="center">
          <TextInput
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Előadó és/vagy cím (pl. Jacob Gurevitsch - Lovers in Paris)"
            w="100%"
          />
          <Button onClick={handleSearch} disabled={loading} color={dark ? "violet" : "yellow"}>
            {loading ? <Loader size="sm" /> : "Ajánlás kérése"}
          </Button>
        </Group>

        {seed && (
          <Card withBorder radius="md" mb={12} style={{ background: dark ? "rgba(255,255,255,0.04)" : "#FFFBEC", borderColor: dark ? "#483d8b" : "#FFD966" }}>
            <Text size="sm" c={dark ? "gray.2" : "gray.7"}>
              Talált kiinduló szám: <strong>{seed.title || "?"}</strong> — {seed.artist || "?"}
            </Text>
          </Card>
        )}

        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 16 }}>
          {tracks.map((t) => (
            <Card
              key={t.title}
              withBorder
              radius="md"
              shadow="md"
              style={{
                background: dark ? "rgba(255,255,255,0.06)" : "#FFFDF5",
                borderColor: dark ? "#483d8b" : "#FFD966",
              }}
            >
              <Group justify="space-between" align="center" wrap="nowrap">
                <Group gap="md" align="center" wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      width: 64,
                      height: 64,
                      borderRadius: 12,
                      background: dark ? "rgba(255,255,255,0.08)" : "#f2f2f2",
                      overflow: "hidden",
                      flexShrink: 0,
                    }}
                  >
                    {t.thumbnail ? (
                      <img
                        src={t.thumbnail}
                        alt={t.title}
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                    ) : null}
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <Text fw={700} size="lg" style={{ color: dark ? "#fff" : "#0C1A2A" }} lineClamp={2}>
                      {t.title}
                    </Text>
                    <Text size="sm" c={dark ? "gray.3" : "gray.7"} lineClamp={1}>
                      {t.artist}
                    </Text>
                  </div>
                </Group>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                  <Button
                    component="a"
                    href={t.link || "#"}
                    target={t.link ? "_blank" : undefined}
                    rel="noopener noreferrer"
                    variant="light"
                    color={dark ? "yellow" : "violet"}
                    radius="md"
                    size="sm"
                  >
                    Megnyitás
                  </Button>
                  {t.previewUrl ? (
                    <audio controls style={{ width: 180 }} src={t.previewUrl}>
                      A böngésző nem támogatja az audio lejátszást.
                    </audio>
                  ) : null}
                </div>
              </Group>
            </Card>
          ))}
        </div>
      </Card>
    </div>
  );
}

export { Recommender };
