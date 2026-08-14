import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The API base is read from VITE_API_BASE at build time (see .env.example), so no
// dev proxy is configured here -- the browser calls FastAPI directly and relies on
// the CORS middleware the backend already enables.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    open: true,
  },
})
