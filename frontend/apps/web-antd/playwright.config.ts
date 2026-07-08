import type { PlaywrightTestConfig } from '@playwright/test';

import { devices } from '@playwright/test';

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const browserChannel = process.env.E2E_BROWSER_CHANNEL ?? (process.env.CI ? undefined : 'chrome');

const config: PlaywrightTestConfig = {
  expect: {
    timeout: 10_000,
  },
  forbidOnly: !!process.env.CI,
  outputDir: 'node_modules/.e2e/test-results',
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: browserChannel,
      },
    },
  ],
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'node_modules/.e2e/html' }],
  ],
  retries: process.env.CI ? 1 : 0,
  testDir: './e2e',
  timeout: 60_000,
  use: {
    baseURL,
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: process.env.E2E_SKIP_WEB_SERVER
    ? undefined
    : {
        command: 'pnpm dev --host localhost',
        reuseExistingServer: true,
        timeout: 120_000,
        url: baseURL,
      },
  workers: 1,
};

export default config;
