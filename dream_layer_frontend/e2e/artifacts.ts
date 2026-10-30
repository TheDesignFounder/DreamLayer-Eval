import path from 'node:path';
import { mkdirSync } from 'node:fs';

export const api = process.env.RESEARCH_API_URL || 'http://127.0.0.1:5055';
export function artifactPath(...parts: string[]) {
  if (!process.env.DLE_VALIDATION_DIR) throw new Error('Playwright run artifact directory is missing');
  const output = path.join(process.env.DLE_VALIDATION_DIR, ...parts);
  mkdirSync(path.dirname(output), {recursive: true});
  return output;
}
