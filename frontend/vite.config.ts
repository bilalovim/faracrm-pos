import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  server: {
    host: process.env.DOCKER === 'true' ? '0.0.0.0' : '127.0.0.1',
    port: 5173,
  },
  // optimizeDeps: {
  // exclude: ['.vite'],
  // entries: ['./src/**/*.{js,jsx,ts,tsx}'],
  // },
  // resolve: {
  //   alias: {
  //     // /esm/icons/index.mjs only exports the icons statically, so no separate chunks are created
  //     '@tabler/icons-react': '@tabler/icons-react/dist/esm/icons/index.mjs',
  //   },
  // },
  // Предбандлим тяжёлые/«многофайловые» зависимости ОДИН раз на старте
  // dev-сервера, чтобы Vite не «открывал» их лениво при первом заходе на
  // очередную модель и не перезапускал оптимизатор с полной перезагрузкой
  // страницы (это и давало «долгий лоадер» между /users, /partners и т.д.).
  //   • @tabler/icons-react — тысячи отдельных icon-модулей, главный виновник.
  //   • react-markdown/remark-gfm — тянут за собой десятки мелких ESM (micromark,
  //     mdast-*), которые всплывают при первом открытии справки (Docs).
  // На production-сборку (npm run build) это НЕ влияет — только dev-опыт.
  optimizeDeps: {
    include: [
      '@tabler/icons-react',
      'react-markdown',
      'remark-gfm',
      'mantine-datatable',
    ],
  },
});
