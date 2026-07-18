import { expect, test } from '@playwright/test';

import { apiBaseURL, getApiToken, loginAsAdmin, uniqueName } from './helpers';

const defaultTenantId = '00000000-0000-4000-8000-000000000001';

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

test('tenant switching keeps Items isolated', async ({ page, request }) => {
  const suffix = uniqueName('tenant-isolation');
  const tenantName = `E2E Tenant ${suffix}`;
  const defaultItemTitle = `default-${suffix}`;
  const tenantItemTitle = `isolated-${suffix}`;
  let defaultToken = await getApiToken(request);
  let tenantToken: string | undefined;
  let tenantId: string | undefined;
  let defaultItemId: string | undefined;
  let tenantItemId: string | undefined;

  try {
    const defaultItemResponse = await request.post(`${apiBaseURL}/items`, {
      data: { title: defaultItemTitle },
      headers: authHeaders(defaultToken),
    });
    expect(defaultItemResponse.ok()).toBeTruthy();
    defaultItemId = ((await defaultItemResponse.json()) as { id: string }).id;

    const tenantResponse = await request.post(`${apiBaseURL}/tenants`, {
      data: {
        code: suffix,
        name: tenantName,
      },
      headers: authHeaders(defaultToken),
    });
    expect(tenantResponse.ok()).toBeTruthy();
    tenantId = ((await tenantResponse.json()) as { id: string }).id;

    const switchResponse = await request.post(`${apiBaseURL}/tenants/switch`, {
      data: { tenant_id: tenantId },
      headers: authHeaders(defaultToken),
    });
    expect(switchResponse.ok()).toBeTruthy();
    tenantToken = ((await switchResponse.json()) as { access_token: string })
      .access_token;

    const tenantItemResponse = await request.post(`${apiBaseURL}/items`, {
      data: { title: tenantItemTitle },
      headers: authHeaders(tenantToken),
    });
    expect(tenantItemResponse.ok()).toBeTruthy();
    tenantItemId = ((await tenantItemResponse.json()) as { id: string }).id;

    await loginAsAdmin(page);
    await page.goto('/items');
    await expect(page.getByText(defaultItemTitle)).toBeVisible();
    await expect(page.getByText(tenantItemTitle)).toHaveCount(0);

    await page.getByRole('button', { name: '切换租户' }).click();
    await page.getByText(tenantName, { exact: true }).click();
    await page.waitForURL('**/dashboard');
    await page.goto('/items');
    await expect(page.getByText(tenantItemTitle)).toBeVisible();
    await expect(page.getByText(defaultItemTitle)).toHaveCount(0);
  } finally {
    if (tenantToken && tenantItemId) {
      await request.delete(`${apiBaseURL}/items/${tenantItemId}`, {
        headers: authHeaders(tenantToken),
      });
    }
    if (tenantToken) {
      const switchBackResponse = await request.post(
        `${apiBaseURL}/tenants/switch`,
        {
          data: { tenant_id: defaultTenantId },
          headers: authHeaders(tenantToken),
        },
      );
      if (switchBackResponse.ok()) {
        defaultToken = (
          (await switchBackResponse.json()) as { access_token: string }
        ).access_token;
      }
    }
    if (defaultItemId) {
      await request.delete(`${apiBaseURL}/items/${defaultItemId}`, {
        headers: authHeaders(defaultToken),
      });
    }
    if (tenantId) {
      await request.delete(`${apiBaseURL}/tenants/${tenantId}`, {
        headers: authHeaders(defaultToken),
      });
    }
  }
});

test('admin can configure a tenant initialization template', async ({
  page,
  request,
}) => {
  test.setTimeout(90_000);
  const token = await getApiToken(request);
  const code = uniqueName('tenant-template');
  const name = `初始化模板-${code}`;
  const updatedName = `${name}-更新`;
  let templateId: string | undefined;

  try {
    await loginAsAdmin(page);
    await page.goto('/system/tenant-templates');

    await page.getByRole('button', { name: '新增开通模板' }).click();
    const createDrawer = page.getByRole('dialog', { name: '新增开通模板' });
    await createDrawer.getByRole('textbox', { name: '模板名称' }).fill(name);
    await createDrawer.getByRole('textbox', { name: '模板编码' }).fill(code);
    await createDrawer
      .getByRole('textbox', { name: '根部门编码' })
      .fill('root-e2e');
    await createDrawer
      .getByRole('textbox', { name: '根部门名称' })
      .fill('E2E 总部');
    await createDrawer.getByRole('button', { name: /确\s*认/ }).click();
    await expect(page.getByText(name)).toBeVisible();

    const listResponse = await request.get(`${apiBaseURL}/tenants/templates`, {
      headers: authHeaders(token),
      params: { keyword: code },
    });
    expect(listResponse.ok()).toBeTruthy();
    const listBody = (await listResponse.json()) as {
      items: Array<{ id: string }>;
    };
    templateId = listBody.items[0]?.id;
    expect(templateId).toBeTruthy();

    const row = page.getByRole('row').filter({ hasText: code });
    await row.getByRole('button', { name: '修改' }).click();
    const editDrawer = page.getByRole('dialog', { name: '编辑开通模板' });
    await editDrawer
      .getByRole('textbox', { name: '模板名称' })
      .fill(updatedName);
    await editDrawer.getByRole('button', { name: /确\s*认/ }).click();
    await expect(page.getByText(updatedName)).toBeVisible();

    await page.goto('/system/tenants');
    await page.getByRole('button', { name: '新增租户' }).click();
    const tenantDrawer = page.getByRole('dialog', { name: '新增租户' });
    await expect(tenantDrawer).toBeVisible();
    const templateSelect = tenantDrawer.getByRole('combobox', {
      name: /初始化模板/,
    });
    await templateSelect.focus();
    await templateSelect.press('ArrowDown');
    const templateOption = page.getByRole('option', { name: updatedName });
    await expect(templateOption).toBeAttached();
    await tenantDrawer.getByRole('button', { name: /取\s*消/ }).click();
  } finally {
    if (templateId) {
      await request.delete(`${apiBaseURL}/tenants/templates/${templateId}`, {
        headers: authHeaders(token),
      });
    }
  }
});
