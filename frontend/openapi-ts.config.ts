import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  client: '@hey-api/client-axios',
  input: process.env.OPENAPI_INPUT ?? 'http://localhost:8000/api/v1/openapi.json',
  output: process.env.OPENAPI_OUTPUT ?? 'apps/web-antd/src/api/generated/platform',
  plugins: ['@hey-api/typescript', '@hey-api/sdk'],
});
