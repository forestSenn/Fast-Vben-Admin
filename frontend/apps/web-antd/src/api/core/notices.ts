import type {
  NoticeCreate,
  NoticePublic,
  NoticesPublic,
  NoticeUpdate,
  UserMessagePublic,
  UserMessagesPublic,
} from '#/api/generated';

import { requestClient } from '#/api/request';

export type NoticeRecord = NoticePublic;
export type NoticeListResult = NoticesPublic;
export type NoticePayload = NoticeCreate;
export type NoticeUpdatePayload = NoticeUpdate;

export type UserMessageRecord = UserMessagePublic;
export type UserMessageListResult = UserMessagesPublic;

export interface NoticeListParams {
  keyword?: string;
  page?: number;
  page_size?: number;
  status?: string;
}

export interface MessageListParams {
  is_read?: boolean;
  page?: number;
  page_size?: number;
}

export function listNoticesApi(params: NoticeListParams = {}) {
  return requestClient.get<NoticeListResult>('/notices', { params });
}

export function createNoticeApi(data: NoticePayload) {
  return requestClient.post<NoticeRecord>('/notices', data);
}

export function updateNoticeApi(noticeId: string, data: NoticeUpdatePayload) {
  return requestClient.request<NoticeRecord>(`/notices/${noticeId}`, {
    data,
    method: 'PATCH',
  });
}

export function publishNoticeApi(noticeId: string) {
  return requestClient.post<NoticeRecord>(`/notices/${noticeId}/publish`);
}

export function withdrawNoticeApi(noticeId: string) {
  return requestClient.post<NoticeRecord>(`/notices/${noticeId}/withdraw`);
}

export function deleteNoticeApi(noticeId: string) {
  return requestClient.delete<void>(`/notices/${noticeId}`);
}

export function listCurrentNoticesApi() {
  return requestClient.get<NoticeRecord[]>('/notices/current');
}

export function listMyMessagesApi(params: MessageListParams = {}) {
  return requestClient.get<UserMessageListResult>('/messages/me', { params });
}

export function markMessageReadApi(messageId: string) {
  return requestClient.post<UserMessageRecord>(`/messages/${messageId}/read`);
}
