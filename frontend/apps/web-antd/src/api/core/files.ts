import type { FileAssetPublic, FileAssetsPublic } from '#/api/generated';

import { requestClient } from '#/api/request';

export type FileAssetRecord = FileAssetPublic;
export type FileAssetListResult = FileAssetsPublic;

export interface FileAssetListParams {
  keyword?: string;
  page?: number;
  page_size?: number;
}

export function listFilesApi(params: FileAssetListParams = {}) {
  return requestClient.get<FileAssetListResult>('/files', { params });
}

export function uploadFileApi(file: File, isPublic = false) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('is_public', String(isPublic));

  return requestClient.post<FileAssetRecord>('/files/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
}

export function deleteFileApi(fileId: string) {
  return requestClient.delete<void>(`/files/${fileId}`);
}

export function getFileDownloadUrl(fileId: string) {
  return `/files/${fileId}/download`;
}
