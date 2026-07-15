import { expect, test } from '@playwright/test';

import { promises as fs } from 'node:fs';

import {
  confirmDeleteDialog,
  loginAsAdmin,
  uniqueName,
} from './helpers';

test('admin can upload, download, and delete a file', async ({ page }, testInfo) => {
  const fileName = `${uniqueName('e2e-file')}.txt`;
  const filePath = testInfo.outputPath(fileName);
  await fs.writeFile(filePath, 'file content from e2e');

  await loginAsAdmin(page);
  await page.goto('/basic-settings/files/list');

  await page.getByRole('button', { name: '上传文件' }).click();
  const uploadDialog = page.getByRole('dialog', { name: '上传文件' });
  await uploadDialog.locator('input[type="file"]').setInputFiles(filePath);
  await expect(page.getByText(fileName)).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: '下载' }).first().click(),
  ]);
  expect(download.suggestedFilename()).toBe(fileName);

  await page.getByRole('button', { name: '删除' }).first().click();
  await confirmDeleteDialog(page, '确认删除文件');
  await expect(page.getByText(fileName)).toHaveCount(0);
});
