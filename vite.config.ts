import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Custom plugin to remove crossorigin and type="module" attributes
const removeModuleAndCrossoriginPlugin = {
  name: 'remove-module-and-crossorigin',
  transformIndexHtml(html: string) {
    return html
      .replace(/\s*crossorigin(="anonymous")?\s*/g, '') // Remove crossorigin
      .replace(/\s*type="module"\s*/g, ''); // Remove type="module"
  },
};

export default defineConfig({
  plugins: [react(), removeModuleAndCrossoriginPlugin],
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        assetFileNames: 'assets/[name]-[hash][extname]',
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
      },
    },
  },
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
});