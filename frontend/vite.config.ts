
import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    outDir: '../backend/static', // emit directly into backend static dir
    emptyOutDir: true
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/health': 'http://localhost:8080'
    }
  }
})
