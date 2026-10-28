import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5173' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'uv run --directory ../backend uvicorn app.main:app --port 8000',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
    },
    {
      // Start exactly as a developer does, so the IPv4 binding in vite.config.ts is tested.
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
    },
  ],
})
