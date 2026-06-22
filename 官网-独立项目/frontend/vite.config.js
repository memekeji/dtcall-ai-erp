import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            '/api': 'http://127.0.0.1:8099',
            '/sitemap.xml': 'http://127.0.0.1:8099',
            '/robots.txt': 'http://127.0.0.1:8099'
        }
    },
    build: {
        outDir: 'dist',
        sourcemap: false
    }
});
