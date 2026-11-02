import { defineConfig, devices } from '@playwright/test';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

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
      command: 'python3 -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8001',
      url: BACKEND_URL + '/',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --port 3000',
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
  ],
});
