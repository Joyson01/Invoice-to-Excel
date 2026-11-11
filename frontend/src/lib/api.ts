export async function readJson<T>(response: Response): Promise<T> {
  const body = await response.text();

  if (!body.trim()) {
    throw new Error(`API returned an empty response (HTTP ${response.status})`);
  }

  let data: any;
  try {
    data = JSON.parse(body);
  } catch {
    throw new Error(`API returned invalid JSON (HTTP ${response.status})`);
  }
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item: { loc?: string[]; msg: string }) => `${item.loc?.join('.') || 'Field'}: ${item.msg}`).join('; ')
      : data.detail;
    throw new Error(detail || `Request failed (HTTP ${response.status})`);
  }
  return data as T;
}

