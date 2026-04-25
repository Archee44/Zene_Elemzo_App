import React from 'react';
import { Button } from '@mantine/core';

export default function LoginWithSpotify() {
  const handleLogin = () => {
    window.location.href = "http://127.0.0.1:5000/api/spotify/login";
  };

  return (
    <div style={{ textAlign: "center", marginTop: "4rem" }}>
      <h2>Spotify kapcsolat</h2>
      <Button color="green" size="md" onClick={handleLogin}>
        Spotify bejelentkezés
      </Button>
    </div>
  );
}
