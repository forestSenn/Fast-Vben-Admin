import { expect, test } from '@playwright/test';

import {
  confirmDeleteDialog,
  confirmDialog,
  loginAsAdmin,
  uniqueName,
} from './helpers';

test('admin can create, edit, and delete an item', async ({ page }) => {
  const title = uniqueName('e2e-item');
  const updatedTitle = `${title}-updated`;

  await loginAsAdmin(page);
  await page.goto('/items');

  await page.getByRole('button', { name: '新增资源' }).click();
  const modal = page.locator('.ant-modal').filter({ hasText: '新增资源' });
  await modal.locator('input').first().fill(title);
  await modal.locator('textarea').first().fill('E2E item description');
  await confirmDialog(modal);
  await expect(page.getByText(title)).toBeVisible();

  await page
    .getByRole('row')
    .filter({ hasText: title })
    .getByRole('button', { name: '编辑' })
    .click();
  const editModal = page.locator('.ant-modal').filter({ hasText: '编辑资源' });
  await editModal.locator('input').first().fill(updatedTitle);
  await confirmDialog(editModal);
  await expect(page.getByText(updatedTitle)).toBeVisible();

  await page
    .getByRole('row')
    .filter({ hasText: updatedTitle })
    .getByRole('button', { name: '删除' })
    .click();
  await confirmDeleteDialog(page, '删除资源');
  await expect(page.getByText(updatedTitle)).toHaveCount(0);
});
