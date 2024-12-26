import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  assetsInclude: ['assets/*'],
  server: {
    port: 5173,
  },
  preview: {
    port: 5173,
  },
  build: {
    sourcemap: process.env.WITH_SOURCE_MAPS === 'true',
  },
});
