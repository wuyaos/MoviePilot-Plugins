import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
export default defineConfig({
  plugins: [vue(), federation({ name: 'ForumSignin', filename: 'remoteEntry.js',
    exposes: { './Config': './src/Config.vue', './Page': './src/Page.vue' },
    shared: { vue: { requiredVersion: false, generate: false } },
  })],
  build: { target: 'esnext', outDir: '../dist', emptyOutDir: true, minify: true },
})
