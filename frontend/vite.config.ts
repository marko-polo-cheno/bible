import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './', // Add '/bible/ for GitHub Pages deployment
  resolve: {
    // Ensure a single React instance (react-router-dom pulled in a duplicate)
    dedupe: ['react', 'react-dom']
  }
});
