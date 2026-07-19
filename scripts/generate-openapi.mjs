import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(scriptDir, '..');
const backendDir = join(rootDir, 'backend');
const frontendDir = join(rootDir, 'frontend');
const generatedRoot = join(
  frontendDir,
  'apps/web-antd/src/api/generated',
);
const generatedModulePages = join(
  frontendDir,
  'apps/web-antd/src/router/generated-module-pages.ts',
);
const generatedBuildManifest = join(
  frontendDir,
  'apps/web-antd/src/modules/build-manifest.ts',
);

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: rootDir,
    encoding: 'utf8',
    shell: options.shell ?? false,
    stdio: options.capture ? 'pipe' : 'inherit',
    ...options,
  });

  if (result.status !== 0) {
    const detail = result.stderr || result.stdout || '';
    throw new Error(`${command} ${args.join(' ')} failed\n${detail}`);
  }

  return result.stdout;
}

function getEdition() {
  const editionFlag = process.argv.indexOf('--edition');
  const edition =
    editionFlag === -1 ? (process.env.APP_EDITION ?? 'suite') : process.argv[editionFlag + 1];
  if (!edition || edition.startsWith('-')) {
    throw new Error('--edition requires an edition name');
  }
  if (!/^[a-z][a-z0-9_-]*$/.test(edition)) {
    throw new Error(`Invalid edition name: ${edition}`);
  }
  return edition;
}

function extractSpec(openapi, predicate) {
  return {
    ...openapi,
    paths: Object.fromEntries(
      Object.entries(openapi.paths).filter(([path]) => predicate(path)),
    ),
  };
}

function writeSpec(directory, name, spec) {
  const path = join(directory, `${name}.json`);
  writeFileSync(path, JSON.stringify(spec), 'utf8');
  return path;
}

function generateClient(input, output, edition) {
  run('pnpm', ['--dir', frontendDir, 'generate:api'], {
    env: {
      ...process.env,
      APP_EDITION: edition,
      OPENAPI_INPUT: input,
      OPENAPI_OUTPUT: output,
    },
    shell: process.platform === 'win32',
  });
}

const edition = getEdition();
const tempDirectory = mkdtempSync(join(tmpdir(), 'fast-vben-openapi-'));
const manifestJson = run(
  'uv',
  [
    'run',
    'python',
    '-c',
    'import json; from app.modules.manifest import build_manifest; from app.modules.registry import get_module_definitions; manifest = build_manifest(edition="' +
      edition +
      '"); definitions = get_module_definitions(); print(json.dumps({"manifest": manifest.model_dump(), "prefixes": {code: definition.api_prefix for code, definition in definitions.items()}}))',
  ],
  {
    capture: true,
    cwd: backendDir,
    env: { ...process.env, APP_EDITION: edition },
  },
);
const { manifest, prefixes } = JSON.parse(manifestJson);
const openapiJson = run(
  'uv',
  [
    'run',
    'python',
    '-c',
    'import json; from app.main import app; print(json.dumps(app.openapi(), ensure_ascii=False))',
  ],
  {
    capture: true,
    cwd: backendDir,
    env: { ...process.env, APP_EDITION: edition },
  },
);
const openapi = JSON.parse(openapiJson);
const moduleCodes = manifest.modules
  .map((module) => module.code)
  .filter((code) => code !== 'platform');

rmSync(generatedRoot, { force: true, recursive: true });
mkdirSync(generatedRoot, { recursive: true });
const modulePrefixes = moduleCodes.map((code) => prefixes[code]);
const platformSpec = extractSpec(
  openapi,
  (path) => !modulePrefixes.some((prefix) => path.startsWith(prefix)),
);
const platformSpecPath = writeSpec(tempDirectory, 'platform', platformSpec);
generateClient(platformSpecPath, join(generatedRoot, 'platform'), edition);
writeFileSync(
  join(generatedRoot, 'index.ts'),
  "export * from './platform';\n",
  'utf8',
);
writeFileSync(
  generatedBuildManifest,
  `export const buildManifest = ${JSON.stringify(manifest, null, 2)} as const;\n`,
  'utf8',
);

for (const moduleCode of moduleCodes) {
  const prefix = prefixes[moduleCode];
  if (!prefix) {
    throw new Error(`Module ${moduleCode} has no API prefix`);
  }
  const moduleSpecPath = writeSpec(
    tempDirectory,
    moduleCode,
    extractSpec(openapi, (path) => path.startsWith(prefix)),
  );
  const output = join(
    frontendDir,
    `apps/web-antd/src/modules/${moduleCode}/api/generated`,
  );
  generateClient(moduleSpecPath, output, edition);
}

const pageGlobLines = moduleCodes.map(
  (moduleCode) => `  ...import.meta.glob('../modules/${moduleCode}/views/**/*.vue'),`,
);
writeFileSync(
  generatedModulePages,
  [
    "import type { ComponentRecordType } from '@vben/types';",
    '',
    'export const modulePageMap: ComponentRecordType = {',
    ...pageGlobLines,
    '};',
    '',
  ].join('\n'),
  'utf8',
);
