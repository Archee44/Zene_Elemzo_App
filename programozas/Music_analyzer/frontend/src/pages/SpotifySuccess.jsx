import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export default function SpotifySuccess() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const token = params.get("token");

  useEffect(() => {
    if (token) {
      localStorage.setItem("spotify_access_token", token);
      alert("Spotify token sikeresen mentve!");
    }
  }, [token]);

  return (
    <div style={{ textAlign: "center", marginTop: "4rem" }}>
      <h2>Bejelentkezés sikeres ✅</h2>
      <p>Mostantól elérheted a Spotify API-t.</p>
    </div>
  );
}
