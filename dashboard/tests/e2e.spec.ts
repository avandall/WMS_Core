import { test, expect } from '@playwright/test';

// Requires API running at 8000 and dashboard at BASE_URL (default http://localhost:8080)
// Provide E2E_USER and E2E_PASS env vars for login.

const E2E_USER = process.env.E2E_USER || '';
const E2E_PASS = process.env.E2E_PASS || '';

async function ensureLoggedIn(page) {
  await page.goto('/');

  const logoutBtn = page.getByRole('button', { name: /logout/i });
  if (await logoutBtn.isVisible().catch(() => false)) {
    return;
  }

  await page.getByRole('button', { name: /login/i }).click();
  await page.getByLabel(/email/i).fill(E2E_USER);
  await page.getByLabel(/password/i).fill(E2E_PASS);
  await page.getByRole('button', { name: /^login$/i }).click();

  await expect(logoutBtn).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(E2E_USER, { exact: false })).toBeVisible({ timeout: 10_000 });
}

async function goToSection(page, label) {
  await page.getByRole('button', { name: label, exact: false }).click();
}

function hasContent(locator) {
  return locator.isVisible().catch(() => false);
}

test.describe('WMS Dashboard smoke', () => {
  test.skip(() => !E2E_USER || !E2E_PASS, 'E2E_USER/E2E_PASS not provided');

  test('products section shows controls', async ({ page }) => {
    await ensureLoggedIn(page);
    await goToSection(page, 'Products');

    await expect(page.getByRole('heading', { name: /product management/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /add product/i })).toBeVisible();

    const table = page.getByRole('table');
    const emptyState = page.getByText(/no products/i);
    const hasTable = await hasContent(table);
    const hasEmpty = await hasContent(emptyState);
    expect(hasTable || hasEmpty).toBeTruthy();
  });

  test('add product modal opens from products', async ({ page }) => {
    await ensureLoggedIn(page);
    await goToSection(page, 'Products');
    await page.getByRole('button', { name: /add product/i }).click();
    await expect(page.getByRole('heading', { name: /create new product/i })).toBeVisible();
  });

  test('warehouses section renders list or empty state', async ({ page }) => {
    await ensureLoggedIn(page);
    await goToSection(page, 'Warehouses');

    await expect(page.getByRole('heading', { name: /warehouse management/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /add warehouse/i })).toBeVisible();

    const table = page.getByRole('table');
    const emptyState = page.getByText(/no warehouses/i);
    const hasTable = await hasContent(table);
    const hasEmpty = await hasContent(emptyState);
    expect(hasTable || hasEmpty).toBeTruthy();
  });

  test('settings realtime toggle updates status', async ({ page }) => {
    await ensureLoggedIn(page);
    await goToSection(page, 'Settings');

    const toggle = page.locator('#realtime-toggle');
    const status = page.locator('#settings-status');

    await toggle.check();
    await expect(status).toContainText(/realtime updates on/i);

    await toggle.uncheck();
    await expect(status).toContainText(/realtime updates off/i);
  });
});
