import { defineConfig } from '@playwright/test';

// SMOKE_PORT lets two checkouts run their smoke tests at the same time without sharing a server.
const port = Number(process.env.SMOKE_PORT ?? 4173);

export default defineConfig({
  testDir: 'tests',
  timeout: 45_000,
  use: {
    baseURL: `http://localhost:${port}`,
    viewport: { width: 1440, height: 900 },
    launchOptions: { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
  },
  webServer: { command: `npx vite preview --port ${port} --strictPort`, port, reuseExistingServer: true },
});
