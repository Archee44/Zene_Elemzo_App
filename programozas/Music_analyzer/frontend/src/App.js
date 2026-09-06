import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './components/layout';
import MusicAnalyzer from './pages/music_analyzer';
import Search from './pages/search';
import PopularSongs from './pages/popular_songs';

import SpotifyUserPlaylist from './pages/user_playlist';
import Recommender from './pages/recommender';
import Profile from './pages/profile';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<PopularSongs/>} />
        <Route path="music-analyzer" element={<MusicAnalyzer />} />
        <Route path="spotify-login" element={<SpotifyUserPlaylist />} />
        <Route path="spotify-success" element={<SpotifyUserPlaylist />} />
        <Route path="music-recommender" element={<Recommender />} />
        <Route path="search" element={<Search />} />
        <Route path="profile" element={<Profile />} />
        {}
      </Route>
    </Routes>
  );
}

export default App;
