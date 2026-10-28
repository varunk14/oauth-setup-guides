export type AgentEvent =
  | { type: 'step'; step: string; status: 'running' | 'done'; message: string }
  | { type: 'probe'; id: string; target: string; outcome: string; summary: string }
  | { type: 'notice'; message: string }
  | { type: 'no_oauth'; message: string }
  | { type: 'done'; slug: string; cached: boolean; from: 'library' | 'generated' }
  | { type: 'error'; code: string; message: string }

/** Split a Server-Sent Events buffer into parsed events plus the unfinished rest. */
export function parseSse(buffer: string): { events: AgentEvent[]; rest: string } {
  const blocks = buffer.split('\n\n')
  const rest = blocks.pop() ?? ''
  const events: AgentEvent[] = []
  for (const block of blocks) {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data: '))
      .map((line) => line.slice(6))
      .join('\n')
    if (!data) continue
    try {
      events.push(JSON.parse(data) as AgentEvent)
    } catch {
      // Ignore a malformed block rather than breaking the whole stream.
    }
  }
  return { events, rest }
}

/** POST a query and call onEvent for every event until the stream ends. */
export async function streamInvestigation(
  query: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`The server answered HTTP ${response.status}.`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseSse(buffer)
    buffer = parsed.rest
    parsed.events.forEach(onEvent)
  }
  parseSse(buffer + '\n\n').events.forEach(onEvent)
}
