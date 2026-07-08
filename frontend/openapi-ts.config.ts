import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  client: '@hey-api/client-axios',
  input: process.env.OPENAPI_INPUT ?? 'http://localhost:8000/api/v1/openapi.json',
  output: 'apps/web-antd/src/api/generated',
  plugins: ['@hey-api/typescript', '@hey-api/sdk'],
});
