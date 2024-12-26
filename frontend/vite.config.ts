import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/bible/' // Add this line for GitHub Pages deployment
});


// // https://vitejs.dev/config/
// export default defineConfig({
//   plugins: [react()],
//   assetsInclude: ['assets/*'],
//   server: {
//     port: 5173,
//   },
//   preview: {
//     port: 5173,
//   },
//   build: {
//     sourcemap: process.env.WITH_SOURCE_MAPS === 'true',
//   },
// });
