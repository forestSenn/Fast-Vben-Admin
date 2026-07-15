import type {
  TenantCreate,
  TenantInitializationTemplateCreate,
  TenantInitializationTemplatePublic,
  TenantInitializationTemplatesPublic,
  TenantInitializationTemplateUpdate,
  TenantMembershipPublic,
  TenantPlanCreate,
  TenantPlanPublic,
  TenantPlansPublic,
  TenantPlanUpdate,
  TenantPublic,
  TenantsPublic,
  TenantSwitchRequest,
  TenantUpdate,
  Token,
} from '#/api/generated';

import { requestClient } from '#/api/request';

export const DEFAULT_TENANT_ID = '00000000-0000-4000-8000-000000000001';
export const TENANT_MEMBERSHIPS_CHANGED_EVENT =
  'fast-vben:tenant-memberships-changed';

export type TenantRecord = TenantPublic;
export type TenantListResult = TenantsPublic;
export type TenantCreatePayload = TenantCreate;
export type TenantUpdatePayload = TenantUpdate;
export type TenantMembershipRecord = TenantMembershipPublic;
export type TenantPlanRecord = TenantPlanPublic;
export type TenantPlanListResult = TenantPlansPublic;
export type TenantPlanCreatePayload = TenantPlanCreate;
export type TenantPlanUpdatePayload = TenantPlanUpdate;
export type TenantTemplateRecord = TenantInitializationTemplatePublic;
export type TenantTemplateListResult = TenantInitializationTemplatesPublic;
export type TenantTemplateCreatePayload = TenantInitializationTemplateCreate;
export type TenantTemplateUpdatePayload = TenantInitializationTemplateUpdate;

export interface TenantListParams {
  is_active?: boolean;
  keyword?: string;
  page?: number;
  page_size?: number;
}

export interface TenantPlanListParams {
  is_active?: boolean;
  keyword?: string;
  page?: number;
  page_size?: number;
}

export function listTenantsApi(params: TenantListParams = {}) {
  return requestClient.get<TenantListResult>('/tenants', { params });
}

export function createTenantApi(data: TenantCreatePayload) {
  return requestClient.post<TenantRecord>('/tenants', data);
}

export function updateTenantApi(tenantId: string, data: TenantUpdatePayload) {
  return requestClient.request<TenantRecord>(`/tenants/${tenantId}`, {
    data,
    method: 'PATCH',
  });
}

export function archiveTenantApi(tenantId: string) {
  return requestClient.delete(`/tenants/${tenantId}`);
}

export function listMyTenantsApi() {
  return requestClient.get<TenantMembershipRecord[]>('/tenants/me');
}

export async function switchTenantApi(data: TenantSwitchRequest) {
  const token = await requestClient.post<Token>('/tenants/switch', data);
  return {
    accessToken: token.access_token,
    tenantId: token.tenant_id,
  };
}

export function notifyTenantMembershipsChanged() {
  window.dispatchEvent(new Event(TENANT_MEMBERSHIPS_CHANGED_EVENT));
}

export function listTenantPlansApi(params: TenantPlanListParams = {}) {
  return requestClient.get<TenantPlanListResult>('/tenants/plans', { params });
}

export function listSimpleTenantPlansApi() {
  return requestClient.get<TenantPlanRecord[]>('/tenants/plans/simple');
}

export function createTenantPlanApi(data: TenantPlanCreatePayload) {
  return requestClient.post<TenantPlanRecord>('/tenants/plans', data);
}

export function updateTenantPlanApi(
  planId: string,
  data: TenantPlanUpdatePayload,
) {
  return requestClient.request<TenantPlanRecord>(`/tenants/plans/${planId}`, {
    data,
    method: 'PATCH',
  });
}

export function deleteTenantPlanApi(planId: string) {
  return requestClient.delete(`/tenants/plans/${planId}`);
}

export function listTenantTemplatesApi(params: TenantPlanListParams = {}) {
  return requestClient.get<TenantTemplateListResult>('/tenants/templates', {
    params,
  });
}

export function listSimpleTenantTemplatesApi() {
  return requestClient.get<TenantTemplateRecord[]>('/tenants/templates/simple');
}

export function createTenantTemplateApi(data: TenantTemplateCreatePayload) {
  return requestClient.post<TenantTemplateRecord>('/tenants/templates', data);
}

export function updateTenantTemplateApi(
  templateId: string,
  data: TenantTemplateUpdatePayload,
) {
  return requestClient.request<TenantTemplateRecord>(
    `/tenants/templates/${templateId}`,
    { data, method: 'PATCH' },
  );
}

export function deleteTenantTemplateApi(templateId: string) {
  return requestClient.delete(`/tenants/templates/${templateId}`);
}
