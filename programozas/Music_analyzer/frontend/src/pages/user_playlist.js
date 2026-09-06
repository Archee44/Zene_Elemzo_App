import React, { useEffect, useState } from "react";
import { Card, Tooltip, Text, Button, Divider, Accordion, Group, Loader, SimpleGrid, List } from "@mantine/core";
import axios from "axios";
import { IconClock, IconTimeline, IconInfoCircle } from "@tabler/icons-react";
import { Doughnut, Bar } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip as ChartTooltip, Legend, CategoryScale, LinearScale, BarElement } from 'chart.js';
ChartJS.register(ArcElement, ChartTooltip, Legend, CategoryScale, LinearScale, BarElement);

export default function SpotifyUserPlaylist() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [playlists, setPlaylists] = useState([]);
  const [error, setError] = useState(null);
  const [loadingPlaylist, setLoadingPlaylist] = useState({});
  const [tracksPlaylist, setTracksPlaylist] = useState({});
  const [opened, setOpened] = useState(null);
  const [singer, setSinger] = useState({});
  const [avgDuration, setAvgDuration] = useState({});
  const [fullDuration, setFullDuration] = useState({});
  const [genreStats, setGenreStats] = useState({});

  const handleLogin = () => {
    window.location.href = "http://127.0.0.1:5000/api/spotify/login";
  };

  const handleLogOut = () => {
    setUser(null);
    setToken(null);
    setPlaylists([]);
    localStorage.removeItem("spotify_access_token");
  };

  const fetchPlaylistTracks = async (playlistId) => {
    if (!token) return;
    if (tracksPlaylist[playlistId]?.length) return;
    setLoadingPlaylist((slp) => ({ ...slp, [playlistId]: true}))
    try {
      const headers = { Authorization: `Bearer ${token}`};
      // Spotify retired GET /playlists/{id}/tracks in the Feb 2026 Dev Mode
      // migration - it's /items now, and items[].track became items[].item.
      let url = `https://api.spotify.com/v1/playlists/${playlistId}/items?limit=100`;
      const allTracks = [];
      while (url) {
        const res = await axios.get(url, { headers });
        allTracks.push(...res.data.items);
        url = res.data.next;
      }

      const flat = allTracks
        .filter((item) => item.item)
        .map((item) => {
          const tr = item.item;
          return {
            id: tr.id,
            name: tr.name,
            artists: tr.artists.map((a) => a.name).join(", "),
            artistIds: tr.artists.map((a) => a.id),
            album: tr.album.name,
            duration: tr.duration_ms,
            preview_url: tr.preview_url,
            external_url: tr.external_urls.spotify,
            image: 
              tr.album?.images?.[2]?.url ||
              tr.album?.images?.[1]?.url ||
              tr.album?.images?.[0]?.url ||
              null,
          };
        });
        const counts = {};
        flat.forEach((t) => {
          t.artists.split(",")
          .map((name) => name.trim())
          .forEach((name) => {
            if (!name) return;
            counts[name] = (counts[name] || 0) + 1;
          });
      });
      const totalDuration = [];

      flat.forEach((t) => {
        if (!t.duration) return;
        totalDuration.push(t.duration);
        });
      const avg = totalDuration.reduce((a, b) => a + b, 0) / totalDuration.length;
      const sum = totalDuration.reduce((a, b) => a + b, 0);

      const uniqueArtistIds = [...new Set(flat.flatMap((t) => t.artistIds || []))];
      const genreLimit = 50;
      const genreCount = {};

      for (let i = 0; i < uniqueArtistIds.length; i += genreLimit) {
        const chunk = uniqueArtistIds.slice(i, i + genreLimit);
        const artistUrl = "https://api.spotify.com/v1/artists?ids=" + chunk.join(",");

        try{
        const artistRes = await axios.get(artistUrl, { headers });
        const artists = artistRes.data.artists || [];

        artists.forEach((artist) => {
          (artist.genres || []).forEach((g) => {
            const genreName = g.trim().toLowerCase();
            if (!genreName) return;
            genreCount[genreName] = (genreCount[genreName] || 0) + 1;
          });
        });
        } catch (e) {
          console.error("Error fetching artist genres:", e);
        }
      }

      setTracksPlaylist((tp) => ({ ...tp, [playlistId]: flat }));
      setSinger((prev) => ({ ...prev, [playlistId]: counts }));
      setAvgDuration((prev) => ({ ...prev, [playlistId]: avg }));
      setFullDuration((prev) => ({ ...prev, [playlistId]: sum }));
      setGenreStats((prev) => ({ ...prev, [playlistId]: genreCount }));
    } catch (err) {
      const status = err?.response?.status;
      setError(
        status === 401 || status === 403
          ? "Hiányzó engedély a lejátszási lista trackekhez (playlist-read-private). Jelentkezz be újra."
          : "A lejátszási lista trackjeinek lekérése sikertelen."
      );
    } finally {
      setLoadingPlaylist((slp) => ({ ...slp, [playlistId]: false}))
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    const savedToken = localStorage.getItem("spotify_access_token");

    if (urlToken) {
      localStorage.setItem("spotify_access_token", urlToken);
      setToken(urlToken);
      const cleanPath = window.location.pathname || "/";
      window.history.replaceState({}, "", cleanPath);
    } else if (savedToken) {
      setToken(savedToken);
    }
  }, []);

  useEffect(() => {
    if (!token) return;

    const headers = { Authorization: `Bearer ${token}` };

    axios
      .get("https://api.spotify.com/v1/me", { headers })
      .then((res) => {
        setUser(res.data);
      })
      .catch((err) => {
        const status = err?.response?.status;
        setError(
          status === 401 || status === 403
            ? "A hozzáférés lejárt vagy hiányzik az engedély. Jelentkezz be újra."
            : "Felhasználói adatok lekérése sikertelen."
        );
        handleLogOut();
      });

    axios

      .get("https://api.spotify.com/v1/me/playlists?limit=20", { headers })
      .then((res) => setPlaylists(res.data.items || []))
      .catch((err) => {
        const status = err?.response?.status;
        setError(
          status === 401 || status === 403
            ? "Hiányzó engedély a playlistekhez (playlist-read-private). Jelentkezz be újra."
            : "Playlisták lekérése sikertelen."
        );
        if (status === 401 || status === 403) handleLogOut();
      });
  }, [token]);

    useEffect(() => {
      console.log('My playlists:', playlists);
    }, [playlists]);

  

  return (

      <div style={{ maxWidth: "1200px", width: "70%", margin: "0 auto" }}>
      {!token ? (
          <Card shadow="sm" padding="sm"  radius="15px" style={{ textAlign: "center", display: "flex", justifyContent: "center" , alignItems: "center", flexDirection: "column", height: "400px", 
            backgroundColor: "#FFF8E7", border: "2px solid #FFD966",maxWidth: "500px", width: "100%", margin: "0 auto"
          }}>
            <img src="icons/spotify_logo.png" alt="Spotify Logo"  style={{ width: 120, marginBottom: 16, display: "flex"}} />
            <Text style={{ fontSize: 20, fontWeight: 600, marginBottom: 24, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <strong>Spotify bejelentkezés {" "}</strong>
              <Tooltip label="Jelentkezz be, hogy elérjük a profilodat és a lejátszási listáidat.">
              <IconInfoCircle size={14} style={{ cursor: "pointer" }}/>
              </Tooltip>
            </Text>
            <Button onClick={handleLogin} size="md" radius="md" style={{ padding: "10px 18px", fontWeight: 600, 
              backgroundColor: "#FFD966", border: "none", cursor: "pointer", fontSize: "16px", color: "#0C1A2A" }}>
              Bejelentkezés Spotify-val
            </Button>
          </Card>
        ) : (
          <>
            {error && (
              <div style={{ background: "#ffe3e3", color: "#8a1c1c", padding: "10px 12px", borderRadius: 8, marginBottom: 16 }}>
                {error}
              </div>
            )}

            {user ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 24, 
                backgroundColor: "#FFF8E7", border: "2px solid #FFD966", borderRadius: "15px", padding: "12px 0", 
                width: "100%"
                }}>
                {user.images?.[0]?.url && (
                  <img src={user.images[0].url} alt="Profil" width={80} height={80} style={{ borderRadius: "50%", objectFit: "cover", 
                    marginLeft: 24}} />
                )}

                  <Divider orientation="vertical" mx="md" style={{ backgroundColor: "black" }}/>
                  <div style={{ flexDirection: "column", alignItems: "flex-start", justifyContent: "center", lineHeight: 0.5, flexGrow: 1 }}>
                    <h2 style={{ margin: 0, marginTop: 12 }}>Üdv, {user.display_name}!</h2>
                    {}
                  </div>

                  <Divider orientation="vertical" mx="md" style={{ color: "black" }}/>

                  <Button onClick={handleLogOut} style={{ padding: "8px 12px", marginRight: 24, backgroundColor: "#FFD966", 
                    color: "#0C1A2A" 
                  }}>
                    Kijelentkezés
                  </Button>

              </div>
            ) : (
              <p>Profil betöltése…</p>
            )}

            <div style={{ backgroundColor: "#FFF8E7", border: "2px solid #FFD966", 
              borderRadius: "15px", height: "60px", display: "flex", alignItems: "center", 
              justifyContent: "center", marginBottom: "16px", width: "100%" }}>
              <h2>Lejátszási listáid</h2>
            </div>
            
            {playlists.length === 0 ? (
              <p>Nincs megjeleníthető playlist, vagy még tölt.</p>
            ) : (
              <Accordion multiple={false} value={opened} onChange={(val) => {
                setOpened(val);
                const pl = playlists.find((p) => p.id === val);
                if (pl) fetchPlaylistTracks(pl.id);
              }}
              variant="contained" radius="md" style={{ backgroundColor: "#FFF8E7", 
                border: "2px solid #FFD966", padding: "16px", borderRadius: "15px", 
                width: "100%"
              }}
              >

                {playlists.map((pl) => (
                  <Accordion.Item key={pl.id} value={pl.id}>
                    <Accordion.Control>
                      <Group gap="md" wrap="nowrap">
                        <div style={{ width: 36, height: 36, borderRadius: 6, overflow: "hidden",
                          background: "#FFF8E7", flex: "0 0 auto" }}>
                          {pl.images?.[0]?.url && (
                            <img src={pl.images[0].url} alt={pl.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                          )}
                        </div>
                        <div>
                          <Text fw={600} size="sm" lineClamp={1}>{pl.name}</Text>
                          <Text size="xs" c="dimmed">{pl.tracks?.total ?? 0 } dal
                            - {pl.owner?.display_name || "Ismeretlen"}
                          </Text>
                        </div>
                      </Group>
                    </Accordion.Control>
                    
                    <Accordion.Panel>
                      {singer[pl.id] && (() => {
                          const data = Object.entries(singer[pl.id])
                            .sort((a, b) => b[1] - a[1])
                            .slice(0, 5);
                          
                          const labels = data.map(([name]) => name);
                          const values = data.map(([, count]) => count);
                          const doughnut = {
                            labels,
                            datasets: [
                              {
                                data: values,
                                backgroundColor: [
                                  '#FF6384',
                                  '#36A2EB',
                                  '#FFCE56',
                                  '#4BC0C0',
                                  '#9966FF']
                              },
                            ],
                          };

                          const barData = Object.entries(genreStats[pl.id])
                            .sort((a, b) => b[1] - a[1])
                            .slice(0, 5);
                            
                            const genreLabels = barData.map(([name]) => name);
                            const genreValues = barData.map(([, count]) => count);
                            const bar = {
                              labels: genreLabels,
                              datasets: [
                                {
                                  data: genreValues,
                                  backgroundColor: '#36A2EB',
                                },
                              ],
                            };    

                          const options = {
                            plugins: {
                              legend: {
                                position: "bottom",
                              },
                            },
                            maintinanceAspectRatio: false,                       
                        };

                          const barOptions = {
                            plugins: {
                              legend: {
                                display: false,
                              }},
                            maintinanceAspectRatio: false,                       
                        };

                      

                          return (
                            <div style={{ maxWidth: "100%", marginBottom: 24, textAlign: "center" }}>
                              
                              <div style={{ width: "100%", height: 360, justifyContent: "center", alignItems: "center", display: "flex", margin: "0 auto" }}>

            
                                    <SimpleGrid cols={2}
                                      spacing={{ base: 10, sm: 'xl' }}
                                      verticalSpacing={{ base: 'md', sm: 'xl' }}>
                                      <div style={{ height: "360px" }}>
                                        <Text size="20px" fw={600} mb={8}>Leggyakoribb előadóid a lejátszási listában</Text>
                                        <Doughnut data={doughnut} options={options}/>
                                      </div>
                                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", radius: 8 }}>
                                        <List size="20px" spacing="md" center listStyleType="none">
                                          <List.Item>
                                          
                                            <Text size="20px" fw={600} mb={8} style={{ marginTop: 8, marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
                                              <IconTimeline size={32} style={{ marginTop: 4, marginBottom: 4 }}/>Átlagos dalhossz: {(avgDuration[pl.id] / 60000).toFixed(2)} perc</Text>
                                          </List.Item>
                                          <List.Item>
                                            <Text size="20px" fw={600} mb={8} style={{ marginTop: 8, marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
                                              <IconClock size={32} style={{ marginTop: 4, marginBottom: 4 }}/>Teljes lejátszási idő: {(fullDuration[pl.id] / 3600000).toFixed(2)} óra</Text>                                      
                                          </List.Item>
                                          <List.Item>
                                            <Text fw={600} size="20px" mb={4}>Leggyakoribb műfajok a playlistben:</Text>
                                            <Bar data={bar} options={barOptions} />
                                          </List.Item>
                                        </List>
                                      </div>      

                                    </SimpleGrid>

                                
                                
                              </div>
                            </div>
                          );
                        })()}
                            
                          

                      {loadingPlaylist[pl.id] ? (
                        <Group gap="xs">
                          <Loader size="sm" />
                          <Text>Dalok betöltése...</Text>
                        </Group>
                        ) : tracksPlaylist[pl.id]?.length ? (
                        <div style={{ border: "1px solid #FFD966", borderRadius: 12 }}>
                          {tracksPlaylist[pl.id].map((t) => (
                            <div
                              key={t.id}
                              style={{
                                display: "grid",
                                gridTemplateColumns: "auto 2fr 1.5fr 1fr auto",
                                alignItems: "center",
                                gap: "12px",
                                padding: "10px 12px",
                                borderBottom: "1px solid #FFD966",
                              }}
                            >
                              <div
                                style={{
                                  width: 36,
                                  height: 36,
                                  borderRadius: 6,
                                  overflow: "hidden",
                                  background: "#f3f3f3",
                                }}
                              >
                                {t.image && (
                                  <img
                                    src={t.image}
                                    alt={t.name}
                                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                                  />
                                )}
                              </div>
                              <div style={{ fontWeight: 600, minWidth: 0 }}>
                                <Text size="sm" lineClamp={1}>{t.name}</Text>
                              </div>
                              <div style={{ opacity: 0.85, minWidth: 0 }}>
                                <Text size="sm" lineClamp={1}>{t.artists}</Text>
                              </div>
                              <div style={{ opacity: 0.7, minWidth: 0 }}>
                                <Text size="sm" lineClamp={1}>{t.album}</Text>
                              </div>
                              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                                {}
                                  <img
                                    src='/icons/youtube_logo.png'
                                    alt='YouTube'
                                    width='32px'
                                    height='32px'
                                    style={{ cursor: 'pointer' }}
                                    onClick={async () => {
                                      try {
                                        const query = `${t.artists} ${t.name}`;
                                        const res = await fetch(`http://localhost:5000/api/music/youtube?q=${encodeURIComponent(query)}`);
                                        const data = await res.json();
                                        if (data.video_url) {
                                          window.open(data.video_url, '_blank');
                                        } else {
                                          alert('Nem található konkrét YouTube videó ehhez a zenéhez.');
                                        }
                                      } catch (error) {
                                        alert('Hiba történt a YouTube keresés során.');
                                        console.error(error);
                                      }
                                    }}
                                  />
                                  <img
                                    src='/icons/spotify_logo.png'
                                    alt='Spotify'
                                    width='32px'
                                    height='32px'
                                    style={{ cursor: 'pointer' }}
                                    onClick={async () => {
                                      try {
                                        const query = `${t.artists} ${t.name}`;
                                        const res = await fetch(`http://localhost:5000/api/music/spotify?q=${encodeURIComponent(query)}`);
                                        const data = await res.json();
                                        if (data.track_url) {
                                          window.open(data.track_url, '_blank');
                                        } else {
                                          alert('Nem található a Spotify-on ez a zene.');
                                        }
                                      } catch (error) {
                                        alert('Hiba történt a Spotify keresés során.');
                                        console.error(error);
                                      }
                                    }}
                                  />
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <Text size="sm" c="dimmed">Nincsenek elérhető dalok ebben a lejátszási listában.</Text>
                      )}
                    </Accordion.Panel>
                  </Accordion.Item>
                ))}
              </Accordion>
            )}
          </>
        )}
      </div>
  );
}
