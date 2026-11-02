import { test, expect } from '@playwright/test';

test.describe('Jev Dashboard E2E', () => {
  test('app loads with title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Jev/i);
  });

  test('API health endpoint responds', async ({ page }) => {
    const response = await page.request.get('/health');
    expect(response.ok()).toBeTruthy();
  });

  test('chat input is visible', async ({ page }) => {
    await page.goto('/');
    const chatInput = page.locator('textarea[placeholder*="Type your message"], textarea').first();
    await expect(chatInput).toBeVisible();
  });

  test('project panel is rendered', async ({ page }) => {
    await page.goto('/');
    const body = await page.content();
    expect(body).toContain('Jev Open Source Dashboard');
  });

  test('attach buttons are visible', async ({ page }) => {
    await page.goto('/');
    const attachBtn = page.locator('button[title*="Attach"]').first();
    await expect(attachBtn).toBeVisible();
  });

  test('command palette opens on Cmd+K', async ({ page }) => {
    await page.goto('/');
    // Wait for the app to hydrate before sending the shortcut
    await page.waitForSelector('textarea[placeholder*="Type your message"], textarea', { timeout: 10000 });
    await page.keyboard.press('Control+k');
    const palette = page.locator('input[placeholder="Type a command…"]').first();
    await expect(palette).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(palette).not.toBeVisible();
  });
});
