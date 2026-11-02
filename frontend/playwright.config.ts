import { defineConfig, devices } from '@playwright/test';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';
// Hermes-managed Python has uvicorn + app deps available
const PLAYWRIGHT_PYTHON = process.env.PLAYWRIGHT_PYTHON || 'python3';
const BACKEND_COMMAND = process.env.PLAYWRIGHT_BACKEND_COMMAND || `bash scripts/start-backend.sh`;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: FRONTEND_URL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: BACKEND_COMMAND,
      url: BACKEND_URL + '/',
      reuseExistingServer: !process.env.CI,
      env: {
        ...process.env,
        TMPDIR: process.env.TMPDIR || '/Users/andrejgorskolepov/.hermes/cache/scratch',
      },
    },
    {
      command: 'npm run dev -- --port 3000',
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
  ],
});
