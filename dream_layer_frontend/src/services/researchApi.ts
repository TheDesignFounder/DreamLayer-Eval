const base = '/api/research';
export async function researchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(base + path, init);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body as T;
}
export const jsonPost = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
