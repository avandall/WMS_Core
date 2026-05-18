import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8080',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
