import { requestClient } from '#/api/request';

export interface BuildManifest {
  edition: string;
  manifest_digest: string;
  modules: Array<{ code: string; version: string }>;
  platform_version: string;
}

export function getBuildManifestApi() {
  return requestClient.get<BuildManifest>('/platform/modules/manifest');
}
