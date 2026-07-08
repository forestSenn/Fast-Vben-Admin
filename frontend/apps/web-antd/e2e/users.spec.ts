import { expect, test } from '@playwright/test';

import {
  confirmDeleteDialog,
  confirmDialog,
  loginAsAdmin,
  uniqueName,
} from './helpers';

test('admin can create and delete a user', async ({ page }) => {
  const email = `${uniqueName('e2e-user')}@example.com`;

  await loginAsAdmin(page);
  await page.goto('/system/users');

  await page.getByRole('button', { name: '新增用户' }).click();
  const modal = page.locator('.ant-modal').filter({ hasText: '新增用户' });
  await modal.locator('input').nth(0).fill(email);
  await modal.locator('input').nth(1).fill('E2E User');
  await modal.locator('input[type="password"]').fill('changethis');
  await confirmDialog(modal);
  await expect(page.getByText(email)).toBeVisible();

  await page
    .getByRole('row')
    .filter({ hasText: email })
    .getByRole('button', { name: '删除' })
    .click();
  await confirmDeleteDialog(page, '删除用户');
  await expect(page.getByText(email)).toHaveCount(0);
});
