import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' keeps every asset path relative, so the same build works on GitHub Pages
// under /<repo>/ and locally. Routes use the hash (#/case/01), so no server rewrites are needed.
export default defineConfig({
  base: './',
  plugins: [react()],
  server: { fs: { allow: ['..'] } },
  build: { chunkSizeWarningLimit: 2000 },
});
