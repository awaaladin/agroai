import { defineConfig } from 'vite';

// The API base URL comes from the environment (VITE_API_BASE), never hard-coded. See .env.example.
export default defineConfig({
  server: { port: 5173, host: true },
  build: { target: 'es2020', sourcemap: false },
});
