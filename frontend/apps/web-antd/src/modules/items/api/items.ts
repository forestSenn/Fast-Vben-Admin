import type {
  ItemCreate,
  ItemPublic,
  ItemsPublic,
} from '#/modules/items/api/generated';

import { requestClient } from '#/api/request';

export type ItemRecord = ItemPublic;

export type ItemListResult = ItemsPublic;

export interface ItemListParams {
  keyword?: string;
  page?: number;
  page_size?: number;
}

export type ItemPayload = ItemCreate;

export function listItemsApi(params: ItemListParams) {
  return requestClient.get<ItemListResult>('/items', { params });
}

export function createItemApi(data: ItemPayload) {
  return requestClient.post<ItemRecord>('/items', data);
}

export function updateItemApi(itemId: string, data: Partial<ItemPayload>) {
  return requestClient.request<ItemRecord>(`/items/${itemId}`, {
    data,
    method: 'PATCH',
  });
}

export function deleteItemApi(itemId: string) {
  return requestClient.delete<void>(`/items/${itemId}`);
}

export function importItemsApi(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return requestClient.post<{
    errors: Array<{ error: string; row: number }>;
    failed: number;
    success: number;
    total: number;
  }>('/items/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
}

export const itemsExportPath = '/items/export';
export const itemsImportTemplatePath = '/items/import-template';
