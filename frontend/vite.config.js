import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      '/start': 'http://127.0.0.1:7860',
      '/sessions': 'http://127.0.0.1:7860',
      '/api': 'http://127.0.0.1:7860',
    },
  },
});
