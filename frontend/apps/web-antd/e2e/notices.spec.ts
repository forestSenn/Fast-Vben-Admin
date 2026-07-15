import { expect, test } from '@playwright/test';

import {
  confirmDeleteDialog,
  confirmDialog,
  loginAsAdmin,
  uniqueName,
} from './helpers';

test('admin can publish a notice and read the generated message', async ({
  page,
}) => {
  const title = uniqueName('e2e-notice');
  const content = `message content for ${title}`;

  await loginAsAdmin(page);
  await page.goto('/system/message-center/notices');

  await page.getByRole('button', { name: '新增公告' }).click();
  const noticeDialog = page.getByRole('dialog', { name: '新增公告' });
  await noticeDialog.getByRole('textbox', { name: /标题/ }).fill(title);
  await noticeDialog.getByRole('textbox', { name: '内容' }).fill(content);
  await confirmDialog(noticeDialog);

  await page.getByRole('textbox', { name: '关键词' }).fill(title);
  await page.getByRole('button', { name: '搜 索' }).click();
  await expect(page.getByRole('row').filter({ hasText: title })).toBeVisible();

  await page.getByRole('button', { name: '发布' }).first().click();
  await page
    .locator('.ant-modal-confirm')
    .getByRole('button', { name: /确\s*定/ })
    .click();
  await expect(page.getByText('已发布').first()).toBeVisible();

  await page.goto('/system/message-center/messages');
  await expect(page.getByText(title)).toBeVisible();
  await page.getByRole('button', { name: '详情' }).first().click();
  const messageDialog = page.getByRole('dialog', { name: '消息详情' });
  await expect(messageDialog.getByText(title, { exact: true })).toBeVisible();
  await expect(messageDialog.getByText(content)).toBeVisible();
  await expect(messageDialog.getByText('已读')).toBeVisible();
  await messageDialog.getByRole('button').first().click();

  await page.goto('/system/message-center/notices');
  await page.getByRole('textbox', { name: '关键词' }).fill(title);
  await page.getByRole('button', { name: '搜 索' }).click();
  await page.getByRole('button', { name: '删除' }).first().click();
  await confirmDeleteDialog(page, '确认删除公告');
  await expect(page.getByText(title)).toHaveCount(0);
});
