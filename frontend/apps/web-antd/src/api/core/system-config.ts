import type {
  DictionaryItemCreate,
  DictionaryItemPublic,
  DictionaryItemsPublic,
  DictionaryItemUpdate,
  DictionaryTypeCreate,
  DictionaryTypePublic,
  DictionaryTypesPublic,
  DictionaryTypeUpdate,
  SystemSettingPublic,
  SystemSettingsPublic,
  SystemSettingUpdate,
} from '#/api/generated';

import { requestClient } from '#/api/request';

export type DictionaryTypeRecord = DictionaryTypePublic;
export type DictionaryTypeListResult = DictionaryTypesPublic;
export type DictionaryTypeCreatePayload = DictionaryTypeCreate;
export type DictionaryTypeUpdatePayload = DictionaryTypeUpdate;

export type DictionaryItemRecord = DictionaryItemPublic;
export type DictionaryItemListResult = DictionaryItemsPublic;
export type DictionaryItemCreatePayload = DictionaryItemCreate;
export type DictionaryItemUpdatePayload = DictionaryItemUpdate;

export type SystemSettingRecord = SystemSettingPublic;
export type SystemSettingListResult = SystemSettingsPublic;
export type SystemSettingUpdatePayload = SystemSettingUpdate;

export interface SystemConfigListParams {
  group?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
  type_id?: string;
}

export function listDictionaryTypesApi(params: SystemConfigListParams = {}) {
  return requestClient.get<DictionaryTypeListResult>('/dictionary-types', {
    params,
  });
}

export function createDictionaryTypeApi(data: DictionaryTypeCreatePayload) {
  return requestClient.post<DictionaryTypeRecord>('/dictionary-types', data);
}

export function updateDictionaryTypeApi(
  typeId: string,
  data: DictionaryTypeUpdatePayload,
) {
  return requestClient.request<DictionaryTypeRecord>(
    `/dictionary-types/${typeId}`,
    {
      data,
      method: 'PATCH',
    },
  );
}

export function deleteDictionaryTypeApi(typeId: string) {
  return requestClient.delete<void>(`/dictionary-types/${typeId}`);
}

export function listDictionaryItemsApi(params: SystemConfigListParams = {}) {
  return requestClient.get<DictionaryItemListResult>('/dictionary-items', {
    params,
  });
}

export function listDictionaryItemsByCodeApi(code: string) {
  return requestClient.get<DictionaryItemRecord[]>(
    `/dictionaries/${encodeURIComponent(code)}/items`,
  );
}

export function createDictionaryItemApi(data: DictionaryItemCreatePayload) {
  return requestClient.post<DictionaryItemRecord>('/dictionary-items', data);
}

export function updateDictionaryItemApi(
  itemId: string,
  data: DictionaryItemUpdatePayload,
) {
  return requestClient.request<DictionaryItemRecord>(
    `/dictionary-items/${itemId}`,
    {
      data,
      method: 'PATCH',
    },
  );
}

export function deleteDictionaryItemApi(itemId: string) {
  return requestClient.delete<void>(`/dictionary-items/${itemId}`);
}

export function listSettingsApi(params: SystemConfigListParams = {}) {
  return requestClient.get<SystemSettingListResult>('/settings', { params });
}

export function listPublicSettingsApi() {
  return requestClient.get<SystemSettingRecord[]>('/settings/public');
}

export function updateSettingApi(
  key: string,
  data: SystemSettingUpdatePayload,
) {
  return requestClient.request<SystemSettingRecord>(
    `/settings/${encodeURIComponent(key)}`,
    {
      data,
      method: 'PATCH',
    },
  );
}
