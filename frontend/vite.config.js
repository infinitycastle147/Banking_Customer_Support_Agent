import { defineConfig } from 'vite';

export default defineConfig({
  envDir: '..',
  envPrefix: ['VITE_', 'NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY'],
  server: {
    proxy: {
      '/start': 'http://127.0.0.1:7860',
      '/sessions': 'http://127.0.0.1:7860',
      '/api': 'http://127.0.0.1:8000',
    },
  },
});
