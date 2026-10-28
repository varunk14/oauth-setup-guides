export interface Health {
  status: string
  schema_version: string
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch('/api/health', { signal })
  if (!response.ok) {
    throw new Error(`Health check failed: HTTP ${response.status}`)
  }
  return (await response.json()) as Health
}
