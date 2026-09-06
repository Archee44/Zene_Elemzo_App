import React, { useState } from "react";
import { Text, Group, Stack, Progress, Avatar, Button, Badge } from "@mantine/core";
import { useMantineColorScheme } from "@mantine/core";
import {
  IconLayoutDashboard,
  IconPlaylist,
  IconHeart,
  IconChartRadar,
  IconSettings,
  IconBrandGoogle,
  IconBrandSpotify,
  IconUpload,
  IconMusic,
  IconThumbUp,
  IconThumbDown,
  IconPlus,
} from "@tabler/icons-react";
import DonutChart from "../components/DonutChart.jsx";
import SectionCard from "../components/SectionCard.jsx";

// --- Mock adatok - csak a dizájn előnézetéhez, backend nélkül ---
const MOCK_USER = {
  name: "Teszt Felhasználó",
  email: "teszt.felhasznalo@gmail.com",
  joined: "2026 szeptember",
};

const MOCK_ACCOUNTS = [
  { provider: "google", label: "Google", connected: true, detail: "teszt.felhasznalo@gmail.com" },
  { provider: "spotify", label: "Spotify", connected: false, detail: null },
];

const MOCK_STATS = { uploads: 12, likes: 47, playlists: 3, analyzed: 59 };

const MOCK_PLAYLISTS = [
  { id: 1, name: "Saját feltöltések", source: "upload", count: 12 },
  { id: 2, name: "YouTube - Reggeli hangulat", source: "youtube", count: 34 },
  { id: 3, name: "Spotify - Edzős lista", source: "spotify", count: 21 },
];

const MOCK_FAVORITES = [
  { id: 1, title: "Intro chiante", artist: "David TMX", genre: "Punk rock" },
  { id: 2, title: "The Rough Guide to Hell", artist: "Kev Bailey", genre: "Instrumental rock" },
  { id: 3, title: "1000 Years (feat. Diag)", artist: "Eugene Naumenko", genre: "Alternative rock" },
  { id: 4, title: "Romantic Moment", artist: "SnakesArt", genre: "Ambient" },
];

const MOCK_GENRE_TASTE = [
  { label: "Rock", value: 34 },
  { label: "Electronic", value: 22 },
  { label: "Hip-Hop", value: 18 },
  { label: "Chill", value: 14 },
  { label: "Jazz-Soul", value: 12 },
];

const MOCK_FEATURES = { energy: 0.72, danceability: 0.58, valence: 0.64, acoustic: 0.31 };

const SOURCE_META = {
  upload: { label: "Saját feltöltés", icon: IconUpload },
  youtube: { label: "YouTube import", icon: IconMusic },
  spotify: { label: "Spotify import", icon: IconBrandSpotify },
};

const TABS = [
  { key: "overview", label: "Áttekintés", icon: IconLayoutDashboard },
  { key: "playlists", label: "Playlistjeim", icon: IconPlaylist },
  { key: "favorites", label: "Kedvenceim", icon: IconHeart },
  { key: "taste", label: "Ízlésprofil", icon: IconChartRadar },
  { key: "settings", label: "Fiókbeállítások", icon: IconSettings },
];

export default function Profile() {
  const { colorScheme } = useMantineColorScheme();
  const dark = colorScheme === "dark";
  const [active, setActive] = useState("overview");

  const accent = dark ? "#a78bfa" : "#c9971f";
  const accentBg = dark ? "#483d8b" : "#FFD966";
  const cardBg = dark ? "#0C1A2A" : "#FFF8E7";
  const cardBorder = dark ? "#483d8b" : "#FFD966";
  const textDim = dark ? "rgba(255,255,255,0.65)" : "rgba(12,26,42,0.6)";

  const donutColors = dark
    ? ["#a78bfa", "#67E8F9", "#34D399", "#FBBF24", "#F59E0B"]
    : ["#7262FD", "#5B8FF9", "#61DDAA", "#F6BD16", "#F6903D"];

  const StatTile = ({ value, label }) => (
    <div
      style={{
        flex: 1,
        minWidth: 110,
        padding: "14px 16px",
        borderRadius: 12,
        background: dark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.6)",
        border: `1px solid ${dark ? "#334155" : "#E5E7EB"}`,
        textAlign: "center",
      }}
    >
      <Text style={{ fontSize: 26, fontWeight: 700, color: accent }}>{value}</Text>
      <Text size="sm" style={{ color: textDim }}>{label}</Text>
    </div>
  );

  const EmptyCta = ({ title, desc, ctaLabel }) => (
    <SectionCard>
      <Group align="flex-start" wrap="nowrap" gap={16}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: "50%",
            background: accentBg,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <IconPlus size={22} color={dark ? "#fff" : "#0C1A2A"} />
        </div>
        <div style={{ flex: 1 }}>
          <Text fw={700}>{title}</Text>
          <Text size="sm" style={{ color: textDim, marginBottom: 10 }}>{desc}</Text>
          <Button
            size="xs"
            radius="md"
            style={{ backgroundColor: accentBg, color: dark ? "#fff" : "#0C1A2A" }}
          >
            {ctaLabel}
          </Button>
        </div>
      </Group>
    </SectionCard>
  );

  return (
    <div style={{ width: "100%", maxWidth: 1100, margin: "0 auto", padding: "0 16px" }}>
      {/* Fejléc: avatar + alapadatok */}
      <SectionCard style={{ marginBottom: 20 }}>
        <Group justify="space-between" wrap="wrap">
          <Group>
            <Avatar radius="xl" size={64} style={{ backgroundColor: accentBg, color: dark ? "#fff" : "#0C1A2A", fontWeight: 700 }}>
              TF
            </Avatar>
            <div>
              <Text fw={700} size="xl">{MOCK_USER.name}</Text>
              <Text size="sm" style={{ color: textDim }}>{MOCK_USER.email}</Text>
              <Text size="xs" style={{ color: textDim }}>Csatlakozott: {MOCK_USER.joined}</Text>
            </div>
          </Group>
          <Group gap={8}>
            {MOCK_ACCOUNTS.map((acc) => (
              <Badge
                key={acc.provider}
                size="lg"
                radius="md"
                variant={acc.connected ? "filled" : "outline"}
                leftSection={acc.provider === "google" ? <IconBrandGoogle size={14} /> : <IconBrandSpotify size={14} />}
                style={{
                  backgroundColor: acc.connected ? accentBg : "transparent",
                  color: acc.connected ? (dark ? "#fff" : "#0C1A2A") : textDim,
                  borderColor: cardBorder,
                  textTransform: "none",
                }}
              >
                {acc.label}{acc.connected ? " - összekapcsolva" : " - nincs összekapcsolva"}
              </Badge>
            ))}
          </Group>
        </Group>
      </SectionCard>

      <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
        {/* Bal oldali navigáció */}
        <div
          style={{
            width: 220,
            flexShrink: 0,
            borderRadius: 15,
            border: `2px solid ${cardBorder}`,
            backgroundColor: cardBg,
            padding: 12,
            position: "sticky",
            top: 90,
          }}
        >
          <Stack gap={4}>
            {TABS.map((t) => {
              const Icon = t.icon;
              const isActive = active === t.key;
              return (
                <div
                  key={t.key}
                  onClick={() => setActive(t.key)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 14px",
                    borderRadius: 10,
                    cursor: "pointer",
                    fontWeight: 600,
                    color: isActive ? (dark ? "#fff" : "#0C1A2A") : textDim,
                    backgroundColor: isActive ? accentBg : "transparent",
                    transition: "background-color 0.15s ease",
                  }}
                >
                  <Icon size={18} />
                  <Text size="sm" fw={600}>{t.label}</Text>
                </div>
              );
            })}
          </Stack>
        </div>

        {/* Tartalom */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {active === "overview" && (
            <Stack gap={16}>
              <SectionCard>
                <Text fw={700} size="lg" style={{ marginBottom: 12 }}>Statisztikák</Text>
                <Group gap={12} wrap="wrap">
                  <StatTile value={MOCK_STATS.uploads} label="Saját feltöltés" />
                  <StatTile value={MOCK_STATS.likes} label="Kedvelt szám" />
                  <StatTile value={MOCK_STATS.playlists} label="Importált playlist" />
                  <StatTile value={MOCK_STATS.analyzed} label="Elemzett szám" />
                </Group>
              </SectionCard>

              <EmptyCta
                title="Importálj egy playlistet"
                desc="Kösd össze a Google vagy Spotify fiókod, és importáld a kedvenc playlistjeidet - ez alapján is finomodik az ajánló."
                ctaLabel="Playlist importálása"
              />
            </Stack>
          )}

          {active === "playlists" && (
            <Stack gap={12}>
              {MOCK_PLAYLISTS.map((pl) => {
                const meta = SOURCE_META[pl.source];
                const Icon = meta.icon;
                return (
                  <SectionCard key={pl.id}>
                    <Group justify="space-between">
                      <Group gap={12}>
                        <div
                          style={{
                            width: 40,
                            height: 40,
                            borderRadius: 10,
                            background: accentBg,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <Icon size={20} color={dark ? "#fff" : "#0C1A2A"} />
                        </div>
                        <div>
                          <Text fw={600}>{pl.name}</Text>
                          <Text size="xs" style={{ color: textDim }}>{meta.label} · {pl.count} szám</Text>
                        </div>
                      </Group>
                    </Group>
                  </SectionCard>
                );
              })}
              <EmptyCta
                title="Új playlist hozzáadása"
                desc="YouTube vagy Spotify fiókodból importálhatsz további listákat."
                ctaLabel="Hozzáadás"
              />
            </Stack>
          )}

          {active === "favorites" && (
            <Stack gap={12}>
              {MOCK_FAVORITES.map((f) => (
                <SectionCard key={f.id}>
                  <Group justify="space-between" wrap="nowrap">
                    <div style={{ minWidth: 0 }}>
                      <Text fw={600} lineClamp={1}>{f.title}</Text>
                      <Text size="sm" style={{ color: textDim }}>{f.artist} · {f.genre}</Text>
                    </div>
                    <Group gap={6}>
                      <Button size="xs" variant="light" radius="xl" color={dark ? "violet" : "yellow"} px={8}>
                        <IconThumbUp size={16} />
                      </Button>
                      <Button size="xs" variant="subtle" radius="xl" color="gray" px={8}>
                        <IconThumbDown size={16} />
                      </Button>
                    </Group>
                  </Group>
                </SectionCard>
              ))}
            </Stack>
          )}

          {active === "taste" && (
            <Stack gap={16}>
              <SectionCard>
                <Text fw={700} size="lg" style={{ marginBottom: 8 }}>Kedvelt műfajok</Text>
                <Group gap={20} align="center">
                  <DonutChart size={160} thickness={24} data={MOCK_GENRE_TASTE} colors={donutColors} />
                  <div style={{ flex: 1 }}>
                    {MOCK_GENRE_TASTE.map((g, i) => (
                      <div key={g.label} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <Group gap={8}>
                            <span style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: donutColors[i % donutColors.length], display: "inline-block" }} />
                            <Text size="sm" fw={600}>{g.label}</Text>
                          </Group>
                          <Text size="sm" style={{ color: textDim }}>{g.value}%</Text>
                        </div>
                      </div>
                    ))}
                  </div>
                </Group>
              </SectionCard>

              <SectionCard>
                <Text fw={700} size="lg" style={{ marginBottom: 12 }}>Jellemző-profil (kedvelt számok átlaga)</Text>
                {Object.entries({
                  Energia: MOCK_FEATURES.energy,
                  Táncolhatóság: MOCK_FEATURES.danceability,
                  Valencia: MOCK_FEATURES.valence,
                  Akusztikusság: MOCK_FEATURES.acoustic,
                }).map(([label, value]) => (
                  <div key={label} style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <Text size="sm" fw={600}>{label}</Text>
                      <Text size="sm" style={{ color: textDim }}>{Math.round(value * 100)}%</Text>
                    </div>
                    <Progress value={value * 100} radius="sm" color={dark ? "violet" : "yellow"} />
                  </div>
                ))}
              </SectionCard>
            </Stack>
          )}

          {active === "settings" && (
            <Stack gap={12}>
              {MOCK_ACCOUNTS.map((acc) => (
                <SectionCard key={acc.provider}>
                  <Group justify="space-between">
                    <Group gap={12}>
                      {acc.provider === "google" ? <IconBrandGoogle size={22} /> : <IconBrandSpotify size={22} />}
                      <div>
                        <Text fw={600}>{acc.label}</Text>
                        <Text size="xs" style={{ color: textDim }}>
                          {acc.connected ? acc.detail : "Nincs összekapcsolva"}
                        </Text>
                      </div>
                    </Group>
                    <Button
                      size="xs"
                      radius="md"
                      variant={acc.connected ? "outline" : "filled"}
                      color={acc.connected ? "red" : (dark ? "violet" : "yellow")}
                      style={!acc.connected ? { backgroundColor: accentBg, color: dark ? "#fff" : "#0C1A2A" } : undefined}
                    >
                      {acc.connected ? "Lecsatlakozás" : "Összekapcsolás"}
                    </Button>
                  </Group>
                </SectionCard>
              ))}
            </Stack>
          )}
        </div>
      </div>
    </div>
  );
}
