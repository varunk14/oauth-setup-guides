import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5199' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // Its own backend on its own port, with no keys and an empty data folder, so tests
      // never depend on a developer's running server or local generated guides.
      command:
        'GENERATED_DIR=$(mktemp -d) OPENAI_API_KEY= GEMINI_API_KEY= TAVILY_API_KEY= ENV_FILE= ' +
        'uv run --directory ../backend uvicorn app.main:app --port 8011',
      url: 'http://127.0.0.1:8011/api/health',
      reuseExistingServer: false,
    },
    {
      // No --host flag, so the 127.0.0.1 binding in vite.config.ts is what the test reaches.
      command: 'API_PORT=8011 npx vite --port 5199 --strictPort',
      url: 'http://127.0.0.1:5199',
      reuseExistingServer: false,
    },
  ],
})
