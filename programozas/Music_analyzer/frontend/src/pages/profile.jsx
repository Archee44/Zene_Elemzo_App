import React, { useEffect, useState } from "react";
import axios from "axios";
import { Text, Group, Stack, Progress, Avatar, Button, Badge, TextInput, Loader } from "@mantine/core";
import { useMantineColorScheme } from "@mantine/core";
import {
  IconLayoutDashboard,
  IconPlaylist,
  IconHeart,
  IconChartRadar,
  IconSettings,
  IconBrandGoogle,
  IconBrandSpotify,
  IconBrandYoutube,
  IconUpload,
  IconThumbUp,
  IconThumbDown,
  IconPlus,
  IconUserCircle,
  IconCheck,
  IconTrash,
  IconDownload,
} from "@tabler/icons-react";
import DonutChart from "../components/DonutChart.jsx";
import SectionCard from "../components/SectionCard.jsx";
import { useAuth } from "../context/AuthContext";

// --- Mock adatok - a Playlistjeim/Kedvenceim/Ízlésprofil fülek egyelőre ezekkel
// mennek, amíg a 2-3. fázis (playlist-import, rating) be nem köti a valódi adatot ---
const MOCK_STATS = { uploads: 12, likes: 47, playlists: 3, analyzed: 59 };

const API_BASE = "http://127.0.0.1:5000/api/music";

const FEATURE_LABELS = {
  energy: "Energia",
  danceability: "Táncolhatóság",
  valence: "Valencia",
  acousticness: "Akusztikusság",
};

const SOURCE_META = {
  upload: { label: "Saját feltöltés", icon: IconUpload },
  youtube: { label: "YouTube import", icon: IconBrandYoutube },
  spotify: { label: "Spotify import", icon: IconBrandSpotify },
};

const PROVIDER_ICON = {
  google: IconBrandGoogle,
  youtube: IconBrandYoutube,
  spotify: IconBrandSpotify,
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
  const { user, token, loading, login, logout, updateUsername, refreshUser, connectYoutube, disconnectYoutube } = useAuth();

  const [usernameInput, setUsernameInput] = useState("");
  const [usernameSaving, setUsernameSaving] = useState(false);
  const [usernameError, setUsernameError] = useState(null);
  const [usernameSaved, setUsernameSaved] = useState(false);

  useEffect(() => {
    setUsernameInput(user?.username || "");
  }, [user?.username]);

  const handleSaveUsername = async () => {
    const trimmed = usernameInput.trim();
    if (!trimmed || trimmed === user?.username) return;
    setUsernameSaving(true);
    setUsernameError(null);
    setUsernameSaved(false);
    const result = await updateUsername(trimmed);
    setUsernameSaving(false);
    if (result.ok) {
      setUsernameSaved(true);
      setTimeout(() => setUsernameSaved(false), 2000);
    } else {
      setUsernameError(result.error);
    }
  };

  const [favorites, setFavorites] = useState({ liked: [], disliked: [] });
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [taste, setTaste] = useState(null);
  const [tasteLoading, setTasteLoading] = useState(false);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogResults, setCatalogResults] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [ratingBusyId, setRatingBusyId] = useState(null);

  const authHeaders = token ? { Authorization: `Bearer ${token}` } : null;

  const fetchFavorites = () => {
    if (!authHeaders) return;
    setFavoritesLoading(true);
    axios
      .get(`${API_BASE}/favorites`, { headers: authHeaders })
      .then((res) => setFavorites(res.data))
      .catch(() => setFavorites({ liked: [], disliked: [] }))
      .finally(() => setFavoritesLoading(false));
  };

  const fetchTaste = () => {
    if (!authHeaders) return;
    setTasteLoading(true);
    axios
      .get(`${API_BASE}/taste-summary`, { headers: authHeaders })
      .then((res) => setTaste(res.data))
      .catch(() => setTaste(null))
      .finally(() => setTasteLoading(false));
  };

  useEffect(() => {
    if (active === "favorites" && user) fetchFavorites();
    if (active === "taste" && user) fetchTaste();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, user]);

  useEffect(() => {
    const q = catalogQuery.trim();
    if (!q) {
      setCatalogResults([]);
      return;
    }
    setCatalogLoading(true);
    const handle = setTimeout(() => {
      axios
        .get(`${API_BASE}/catalog-search`, { params: { q } })
        .then((res) => setCatalogResults(res.data.results || []))
        .catch(() => setCatalogResults([]))
        .finally(() => setCatalogLoading(false));
    }, 350);
    return () => clearTimeout(handle);
  }, [catalogQuery]);

  const handleRate = async (songId, rating) => {
    if (!authHeaders) return;
    setRatingBusyId(songId);
    try {
      await axios.post(`${API_BASE}/songs/${songId}/rate`, { rating }, { headers: authHeaders });
      fetchFavorites();
      if (active === "taste") fetchTaste();
    } catch {
      // silently ignore - the buttons stay in their previous state
    } finally {
      setRatingBusyId(null);
    }
  };

  const likedIds = new Set(favorites.liked.map((f) => f.id));
  const dislikedIds = new Set(favorites.disliked.map((f) => f.id));

  const [myPlaylists, setMyPlaylists] = useState([]);
  const [myPlaylistsLoading, setMyPlaylistsLoading] = useState(false);
  const [ytPlaylists, setYtPlaylists] = useState([]);
  const [ytPlaylistsLoading, setYtPlaylistsLoading] = useState(false);
  const [importBusyId, setImportBusyId] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [openPlaylistId, setOpenPlaylistId] = useState(null);
  const [openPlaylistData, setOpenPlaylistData] = useState(null);
  const [openPlaylistLoading, setOpenPlaylistLoading] = useState(false);

  const fetchMyPlaylists = () => {
    if (!authHeaders) return;
    setMyPlaylistsLoading(true);
    axios
      .get(`${API_BASE}/playlists`, { headers: authHeaders })
      .then((res) => setMyPlaylists(res.data.playlists || []))
      .catch(() => setMyPlaylists([]))
      .finally(() => setMyPlaylistsLoading(false));
  };

  const fetchYoutubePlaylists = () => {
    if (!authHeaders) return;
    setYtPlaylistsLoading(true);
    axios
      .get(`${API_BASE}/youtube-playlists`, { headers: authHeaders })
      .then((res) => setYtPlaylists(res.data.playlists || []))
      .catch(() => setYtPlaylists([]))
      .finally(() => setYtPlaylistsLoading(false));
  };

  useEffect(() => {
    if (active !== "playlists" || !user) return;
    fetchMyPlaylists();
    if (user.youtube_connected) fetchYoutubePlaylists();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, user?.id, user?.youtube_connected]);

  // Handle the return from the YouTube-connect OAuth redirect.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const yt = params.get("youtube");
    if (!yt) return;
    if (yt === "connected") {
      refreshUser();
      setActive("playlists");
    }
    const cleanUrl = new URL(window.location.href);
    cleanUrl.searchParams.delete("youtube");
    window.history.replaceState({}, "", cleanUrl.pathname + cleanUrl.search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleImportPlaylist = async (pl) => {
    if (!authHeaders) return;
    setImportBusyId(pl.id);
    setImportResult(null);
    try {
      const res = await axios.post(
        `${API_BASE}/youtube-playlists/${pl.id}/import`,
        { name: pl.title },
        { headers: authHeaders }
      );
      setImportResult({ playlistTitle: pl.title, ...res.data });
      fetchMyPlaylists();
    } catch {
      setImportResult({ playlistTitle: pl.title, error: true });
    } finally {
      setImportBusyId(null);
    }
  };

  const handleOpenPlaylist = (id) => {
    if (openPlaylistId === id) {
      setOpenPlaylistId(null);
      setOpenPlaylistData(null);
      return;
    }
    setOpenPlaylistId(id);
    setOpenPlaylistLoading(true);
    axios
      .get(`${API_BASE}/playlists/${id}`, { headers: authHeaders })
      .then((res) => setOpenPlaylistData(res.data))
      .catch(() => setOpenPlaylistData(null))
      .finally(() => setOpenPlaylistLoading(false));
  };

  const handleDeletePlaylist = async (id) => {
    if (!authHeaders) return;
    try {
      await axios.delete(`${API_BASE}/playlists/${id}`, { headers: authHeaders });
      if (openPlaylistId === id) {
        setOpenPlaylistId(null);
        setOpenPlaylistData(null);
      }
      fetchMyPlaylists();
    } catch {
      // no-op
    }
  };

  const handleRatePlaylistSong = async (songId, rating) => {
    await handleRate(songId, rating);
    if (openPlaylistId) {
      axios
        .get(`${API_BASE}/playlists/${openPlaylistId}`, { headers: authHeaders })
        .then((res) => setOpenPlaylistData(res.data))
        .catch(() => {});
    }
  };

  const accounts = [
    {
      provider: "google",
      label: "Google",
      connected: !!user,
      detail: user?.email || null,
    },
    {
      provider: "youtube",
      label: "YouTube",
      connected: !!user?.youtube_connected,
      detail: user?.youtube_connected ? "Összekapcsolva" : null,
    },
    { provider: "spotify", label: "Spotify", connected: false, detail: null },
  ];

  const initials = (user?.username || user?.display_name || user?.email || "?")
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

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

  const EmptyCta = ({ title, desc, ctaLabel, onClick, icon: CtaIcon = IconPlus, loading }) => (
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
          <CtaIcon size={22} color={dark ? "#fff" : "#0C1A2A"} />
        </div>
        <div style={{ flex: 1 }}>
          <Text fw={700}>{title}</Text>
          <Text size="sm" style={{ color: textDim, marginBottom: 10 }}>{desc}</Text>
          <Button
            size="xs"
            onClick={onClick}
            loading={loading}
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
        {!loading && !user ? (
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
              <IconBrandGoogle size={22} color={dark ? "#fff" : "#0C1A2A"} />
            </div>
            <div style={{ flex: 1 }}>
              <Text fw={700}>Bejelentkezés</Text>
              <Text size="sm" style={{ color: textDim, marginBottom: 10 }}>
                Jelentkezz be Google-fiókoddal, hogy elmentsük a kedvenceidet és testre szabjuk az ajánlót.
              </Text>
              <Button
                size="xs"
                radius="md"
                onClick={login}
                style={{ backgroundColor: accentBg, color: dark ? "#fff" : "#0C1A2A" }}
              >
                Bejelentkezés Google-lel
              </Button>
            </div>
          </Group>
        ) : (
          <Group justify="space-between" wrap="wrap">
            <Group>
              <Avatar
                radius="xl"
                size={64}
                src={user?.avatar_url}
                style={{ backgroundColor: accentBg, color: dark ? "#fff" : "#0C1A2A", fontWeight: 700 }}
              >
                {initials}
              </Avatar>
              <div>
                <Text fw={700} size="xl">{user?.username || user?.display_name || user?.email || "Betöltés..."}</Text>
                <Text size="sm" style={{ color: textDim }}>{user?.email}</Text>
              </div>
            </Group>
            <Group gap={8}>
              {accounts.map((acc) => {
                const AccIcon = PROVIDER_ICON[acc.provider];
                return (
                <Badge
                  key={acc.provider}
                  size="lg"
                  radius="md"
                  variant={acc.connected ? "filled" : "outline"}
                  leftSection={<AccIcon size={14} />}
                  style={{
                    backgroundColor: acc.connected ? accentBg : "transparent",
                    color: acc.connected ? (dark ? "#fff" : "#0C1A2A") : textDim,
                    borderColor: cardBorder,
                    textTransform: "none",
                  }}
                >
                  {acc.label}{acc.connected ? " - összekapcsolva" : " - nincs összekapcsolva"}
                </Badge>
                );
              })}
              <Button size="xs" variant="subtle" color="red" radius="md" onClick={logout}>
                Kijelentkezés
              </Button>
            </Group>
          </Group>
        )}
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

          {active === "playlists" && (!user ? (
            <EmptyCta
              title="Jelentkezz be"
              desc="Bejelentkezve importálhatod a YouTube playlistjeidet."
              ctaLabel="Bejelentkezés Google-lel"
              onClick={login}
            />
          ) : !user.youtube_connected ? (
            <EmptyCta
              title="Kösd össze a YouTube fiókod"
              desc="Ezután kiválaszthatod, melyik YouTube playlistedet importáljuk - a talált számokat itt tudod majd értékelni."
              ctaLabel="YouTube összekapcsolása"
              icon={IconBrandYoutube}
              onClick={connectYoutube}
            />
          ) : (
            <Stack gap={16}>
              <Text fw={700} size="lg">
                Importált playlistjeid {myPlaylistsLoading && <Loader size="xs" style={{ marginLeft: 8 }} />}
              </Text>
              {!myPlaylistsLoading && myPlaylists.length === 0 && (
                <Text size="sm" style={{ color: textDim }}>Még nincs importált playlisted - válassz egyet alább.</Text>
              )}
              {myPlaylists.map((pl) => {
                const meta = SOURCE_META[pl.source] || SOURCE_META.youtube;
                const Icon = meta.icon;
                const isOpen = openPlaylistId === pl.id;
                return (
                  <SectionCard key={pl.id}>
                    <Group justify="space-between">
                      <Group gap={12} style={{ cursor: "pointer", flex: 1 }} onClick={() => handleOpenPlaylist(pl.id)}>
                        <div
                          style={{
                            width: 40,
                            height: 40,
                            borderRadius: 10,
                            background: accentBg,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}
                        >
                          <Icon size={20} color={dark ? "#fff" : "#0C1A2A"} />
                        </div>
                        <div>
                          <Text fw={600}>{pl.name}</Text>
                          <Text size="xs" style={{ color: textDim }}>{meta.label} · {pl.item_count} szám</Text>
                        </div>
                      </Group>
                      <Button size="xs" variant="subtle" color="red" radius="md" onClick={() => handleDeletePlaylist(pl.id)}>
                        <IconTrash size={16} />
                      </Button>
                    </Group>
                    {isOpen && (
                      <div style={{ marginTop: 12, borderTop: `1px solid ${cardBorder}`, paddingTop: 12 }}>
                        {openPlaylistLoading ? (
                          <Loader size="xs" />
                        ) : !openPlaylistData ? (
                          <Text size="sm" style={{ color: textDim }}>Nem sikerült betölteni.</Text>
                        ) : (
                          <Stack gap={8}>
                            {openPlaylistData.items.map((item, idx) => (
                              <Group key={item.song_id ?? `unmatched-${idx}`} justify="space-between" wrap="nowrap">
                                <div style={{ minWidth: 0 }}>
                                  <Text size="sm" fw={600} lineClamp={1}>{item.title}</Text>
                                  <Text size="xs" style={{ color: textDim }}>{item.artist || "-"}</Text>
                                </div>
                                {item.matched ? (
                                  <Group gap={6}>
                                    <Button
                                      size="xs"
                                      variant={likedIds.has(item.song_id) ? "filled" : "light"}
                                      radius="xl"
                                      color={dark ? "violet" : "yellow"}
                                      px={8}
                                      loading={ratingBusyId === item.song_id}
                                      onClick={() => handleRatePlaylistSong(item.song_id, "like")}
                                    >
                                      <IconThumbUp size={16} />
                                    </Button>
                                    <Button
                                      size="xs"
                                      variant={dislikedIds.has(item.song_id) ? "filled" : "subtle"}
                                      radius="xl"
                                      color="gray"
                                      px={8}
                                      loading={ratingBusyId === item.song_id}
                                      onClick={() => handleRatePlaylistSong(item.song_id, "dislike")}
                                    >
                                      <IconThumbDown size={16} />
                                    </Button>
                                  </Group>
                                ) : (
                                  <Text size="xs" style={{ color: textDim }}>nincs a katalógusban</Text>
                                )}
                              </Group>
                            ))}
                          </Stack>
                        )}
                      </div>
                    )}
                  </SectionCard>
                );
              })}

              <Text fw={700} size="lg" style={{ marginTop: 8 }}>
                YouTube playlistjeid {ytPlaylistsLoading && <Loader size="xs" style={{ marginLeft: 8 }} />}
              </Text>
              {ytPlaylists.map((pl) => (
                <SectionCard key={pl.id}>
                  <Group justify="space-between">
                    <Group gap={12}>
                      <IconBrandYoutube size={22} />
                      <div>
                        <Text fw={600}>{pl.title}</Text>
                        <Text size="xs" style={{ color: textDim }}>{pl.item_count} szám</Text>
                      </div>
                    </Group>
                    <Button
                      size="xs"
                      radius="md"
                      loading={importBusyId === pl.id}
                      leftSection={<IconDownload size={14} />}
                      onClick={() => handleImportPlaylist(pl)}
                      style={{ backgroundColor: accentBg, color: dark ? "#fff" : "#0C1A2A" }}
                    >
                      Importálás
                    </Button>
                  </Group>
                </SectionCard>
              ))}
              {importResult && (
                <SectionCard>
                  {importResult.error ? (
                    <Text size="sm">Hiba történt az importálás közben.</Text>
                  ) : (
                    <Text size="sm">
                      <strong>{importResult.playlistTitle}</strong>: {importResult.matched}/{importResult.total} szám megtalálva a katalógusban.
                    </Text>
                  )}
                </SectionCard>
              )}
            </Stack>
          ))}

          {active === "favorites" && (!user ? (
            <EmptyCta
              title="Jelentkezz be"
              desc="Bejelentkezve tudod menteni és értékelni a kedvenc számaidat."
              ctaLabel="Bejelentkezés Google-lel"
            />
          ) : (
            <Stack gap={16}>
              <SectionCard>
                <Text fw={700} size="lg" style={{ marginBottom: 8 }}>Keress számot értékeléshez</Text>
                <TextInput
                  placeholder="Cím vagy előadó..."
                  value={catalogQuery}
                  onChange={(e) => setCatalogQuery(e.currentTarget.value)}
                  size="sm"
                  radius="md"
                  style={{ marginBottom: 10 }}
                />
                {catalogLoading && <Loader size="xs" />}
                {!catalogLoading && catalogQuery.trim() && catalogResults.length === 0 && (
                  <Text size="sm" style={{ color: textDim }}>Nincs találat.</Text>
                )}
                <Stack gap={8}>
                  {catalogResults.map((r) => (
                    <Group key={r.id} justify="space-between" wrap="nowrap">
                      <div style={{ minWidth: 0 }}>
                        <Text size="sm" fw={600} lineClamp={1}>{r.title}</Text>
                        <Text size="xs" style={{ color: textDim }}>{r.artist}{r.genre ? ` · ${r.genre}` : ""}</Text>
                      </div>
                      <Group gap={6}>
                        <Button
                          size="xs"
                          variant={likedIds.has(r.id) ? "filled" : "light"}
                          radius="xl"
                          color={dark ? "violet" : "yellow"}
                          px={8}
                          loading={ratingBusyId === r.id}
                          onClick={() => handleRate(r.id, "like")}
                        >
                          <IconThumbUp size={16} />
                        </Button>
                        <Button
                          size="xs"
                          variant={dislikedIds.has(r.id) ? "filled" : "subtle"}
                          radius="xl"
                          color="gray"
                          px={8}
                          loading={ratingBusyId === r.id}
                          onClick={() => handleRate(r.id, "dislike")}
                        >
                          <IconThumbDown size={16} />
                        </Button>
                      </Group>
                    </Group>
                  ))}
                </Stack>
              </SectionCard>

              <Text fw={700} size="lg">Kedvelt számaid {favoritesLoading && <Loader size="xs" style={{ marginLeft: 8 }} />}</Text>
              {!favoritesLoading && favorites.liked.length === 0 && (
                <Text size="sm" style={{ color: textDim }}>Még nincs kedvelt számod - keress fentebb egyet.</Text>
              )}
              {favorites.liked.map((f) => (
                <SectionCard key={f.id}>
                  <Group justify="space-between" wrap="nowrap">
                    <div style={{ minWidth: 0 }}>
                      <Text fw={600} lineClamp={1}>{f.title}</Text>
                      <Text size="sm" style={{ color: textDim }}>{f.artist}{f.genre ? ` · ${f.genre}` : ""}</Text>
                    </div>
                    <Group gap={6}>
                      <Button size="xs" variant="filled" radius="xl" color={dark ? "violet" : "yellow"} px={8} disabled>
                        <IconThumbUp size={16} />
                      </Button>
                      <Button
                        size="xs"
                        variant="subtle"
                        radius="xl"
                        color="gray"
                        px={8}
                        loading={ratingBusyId === f.id}
                        onClick={() => handleRate(f.id, "dislike")}
                      >
                        <IconThumbDown size={16} />
                      </Button>
                    </Group>
                  </Group>
                </SectionCard>
              ))}
            </Stack>
          ))}

          {active === "taste" && (!user ? (
            <EmptyCta
              title="Jelentkezz be"
              desc="Bejelentkezve látod majd az ízlésprofilodat a kedvelt számaid alapján."
              ctaLabel="Bejelentkezés Google-lel"
            />
          ) : tasteLoading ? (
            <Loader size="sm" />
          ) : !taste || taste.liked_count === 0 ? (
            <SectionCard>
              <Text fw={700} style={{ marginBottom: 4 }}>Még nincs elég adat</Text>
              <Text size="sm" style={{ color: textDim }}>
                Jelölj kedvencnek pár számot a "Kedvenceim" fülön, és itt megjelenik az ízlésprofilod.
              </Text>
            </SectionCard>
          ) : (
            <Stack gap={16}>
              <SectionCard>
                <Text fw={700} size="lg" style={{ marginBottom: 8 }}>Kedvelt műfajok ({taste.liked_count} szám alapján)</Text>
                <Group gap={20} align="center">
                  <DonutChart size={160} thickness={24} data={taste.genres} colors={donutColors} />
                  <div style={{ flex: 1 }}>
                    {taste.genres.map((g, i) => (
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
                {Object.entries(FEATURE_LABELS).map(([key, label]) => {
                  const value = taste.features?.[key];
                  return (
                    <div key={key} style={{ marginBottom: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <Text size="sm" fw={600}>{label}</Text>
                        <Text size="sm" style={{ color: textDim }}>
                          {value == null ? "nincs adat" : `${Math.round(value * 100)}%`}
                        </Text>
                      </div>
                      <Progress value={value == null ? 0 : value * 100} radius="sm" color={dark ? "violet" : "yellow"} />
                    </div>
                  );
                })}
              </SectionCard>
            </Stack>
          ))}

          {active === "settings" && (
            <Stack gap={12}>
              {user && (
                <SectionCard>
                  <Group gap={12} align="flex-start" wrap="nowrap">
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: 10,
                        background: accentBg,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <IconUserCircle size={20} color={dark ? "#fff" : "#0C1A2A"} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <Text fw={600} style={{ marginBottom: 2 }}>Felhasználónév</Text>
                      <Text size="xs" style={{ color: textDim, marginBottom: 10 }}>
                        Ez jelenik meg a profilodon a Google-fiókból kapott név helyett.
                      </Text>
                      <Group gap={8} align="flex-start" wrap="wrap">
                        <TextInput
                          placeholder="pl. melodive_fan"
                          value={usernameInput}
                          onChange={(e) => setUsernameInput(e.currentTarget.value)}
                          error={usernameError}
                          size="sm"
                          radius="md"
                          style={{ flex: 1, minWidth: 200 }}
                        />
                        <Button
                          size="sm"
                          radius="md"
                          loading={usernameSaving}
                          disabled={!usernameInput.trim() || usernameInput.trim() === user?.username}
                          leftSection={usernameSaved ? <IconCheck size={16} /> : undefined}
                          onClick={handleSaveUsername}
                          style={{ backgroundColor: accentBg, color: dark ? "#fff" : "#0C1A2A" }}
                        >
                          {usernameSaved ? "Mentve" : "Mentés"}
                        </Button>
                      </Group>
                    </div>
                  </Group>
                </SectionCard>
              )}
              {accounts.map((acc) => {
                const AccIcon = PROVIDER_ICON[acc.provider];
                const actions = {
                  google: { connect: login, disconnect: logout },
                  youtube: { connect: connectYoutube, disconnect: disconnectYoutube },
                }[acc.provider];
                return (
                <SectionCard key={acc.provider}>
                  <Group justify="space-between">
                    <Group gap={12}>
                      <AccIcon size={22} />
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
                      onClick={actions ? (acc.connected ? actions.disconnect : actions.connect) : undefined}
                      disabled={!actions}
                    >
                      {acc.connected ? "Lecsatlakozás" : "Összekapcsolás"}
                    </Button>
                  </Group>
                </SectionCard>
                );
              })}
            </Stack>
          )}
        </div>
      </div>
    </div>
  );
}
