import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { mkdirSync, writeFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';

// Workers inherit one run identity. Never replace an earlier run's evidence.
if (!process.env.DLE_VALIDATION_RUN_ID) {
  const runId = new Date().toISOString().replaceAll(':', '-') + '-' + randomUUID().slice(0, 8);
  const directory = path.resolve(process.env.DLE_VALIDATION_DIR || `../.research/validation/browser-runs/${runId}`);
  mkdirSync(path.dirname(directory), {recursive: true});
  mkdirSync(directory); // Existing paths are rejected, including explicit overrides.
  process.env.DLE_VALIDATION_DIR = directory;
  process.env.DLE_VALIDATION_RUN_ID = runId;
  writeFileSync(path.join(directory, 'run.json'), JSON.stringify({run_id: runId, created_at: new Date().toISOString(),
    frontend: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8080',
    api: process.env.RESEARCH_API_URL || 'http://127.0.0.1:5055'}, null, 2));
}
const artifacts = process.env.DLE_VALIDATION_DIR!;
export default defineConfig({
  testDir: './e2e', timeout: 60000, workers: 1,
  outputDir: path.join(artifacts, 'test-results'),
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:8080', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  reporter: [['list'], ['html', { open: 'never', outputFolder: path.join(artifacts, 'html-report') }]],
});
