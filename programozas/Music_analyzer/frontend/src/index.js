import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { MantineProvider } from '@mantine/core';
import { BrowserRouter } from 'react-router-dom';
import '@mantine/core/styles.css';

// "ResizeObserver loop completed with undelivered notifications" is a harmless
// browser-spec warning. @arraypress/waveform-player triggers it: its observer
// callback (resizeCanvas) sets the height of the element it is observing, which
// changes that element's size again within the same frame. Nothing is broken,
// but webpack-dev-server's overlay shows it as a full-screen runtime error.
//
// Swallowing the 'error' event doesn't work: the dev-server overlay registers its
// own window listener before this file runs, and a listener added later (even in
// the capture phase) is not guaranteed to run first. So deliver observer
// callbacks on the next animation frame instead, which moves the size change
// out of the observer's delivery step. Development only - production builds
// don't show the overlay and keep the native behavior.
if (process.env.NODE_ENV !== 'production' && typeof window.ResizeObserver === 'function') {
  const NativeResizeObserver = window.ResizeObserver;
  window.ResizeObserver = class extends NativeResizeObserver {
    constructor(callback) {
      super((entries, observer) => {
        window.requestAnimationFrame(() => callback(entries, observer));
      });
    }
  };
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <MantineProvider withGlobalStyles withNormalizeCSS>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </MantineProvider>
);
