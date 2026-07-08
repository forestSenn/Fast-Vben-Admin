import type { Locator, Page } from '@playwright/test';

import { expect } from '@playwright/test';

export const adminEmail = process.env.E2E_ADMIN_EMAIL ?? 'admin@example.com';
export const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? 'changethis';

export async function loginAsAdmin(page: Page) {
  await page.goto('/auth/login');
  await page.locator('input[name="username"]').fill(adminEmail);
  await page.locator('input[name="password"]').fill(adminPassword);
  await page.getByRole('button', { name: 'login' }).click();
  await expect(page.getByText('仪表盘').first()).toBeVisible();
}

export function uniqueName(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export async function confirmDialog(dialog: Locator) {
  await dialog.getByRole('button', { name: /^(OK|确\s*定)$/ }).click();
}

export async function confirmDeleteDialog(page: Page, title: string) {
  await page
    .getByRole('dialog')
    .filter({ hasText: title })
    .getByRole('button', { name: /^删\s*除$/ })
    .click();
}
