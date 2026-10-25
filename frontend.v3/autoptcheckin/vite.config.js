import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
export default defineConfig({
  plugins: [vue(), federation({ name: 'AutoPtCheckin', filename: 'remoteEntry.js',
    exposes: { './Config': './src/Config.vue', './Page': './src/Page.vue' },
    shared: { vue: { requiredVersion: false, generate: false } },
  })],
  build: { target: 'esnext', outDir: '../../plugins.v3/autoptcheckin/dist', emptyOutDir: true, minify: true },
})
