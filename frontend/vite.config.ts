import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  // The backend defaults to 8080 (see web_api/app.py and docker-compose.yml).
  const apiTarget = env.VITE_API_TARGET || 'http://localhost:8080';

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 3000,
      host: '0.0.0.0',
      // Cookie-based auth needs the API on the same origin during development.
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true, secure: false },
      },
    },
    build: {
      target: 'es2022',
      sourcemap: mode !== 'production',
      rollupOptions: {
        output: {
          manualChunks: {
            editor: ['@codemirror/lang-sql', '@codemirror/view', '@codemirror/state'],
          },
        },
      },
    },
    resolve: {
      alias: { '@': path.resolve(__dirname, '.') },
    },
  };
});
