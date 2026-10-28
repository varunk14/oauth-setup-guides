import { describe, expect, it } from 'vitest'
import { parseSse } from './sse'

describe('parseSse', () => {
  it('parses complete events and keeps the unfinished rest', () => {
    const text =
      'event: step\ndata: {"type":"step","step":"research","status":"running","message":"go"}\n\n' +
      'event: done\ndata: {"type":"done","slug":"zoom","cached":false,"from":"generated"}\n\n' +
      'event: probe\ndata: {"type":"pro'
    const { events, rest } = parseSse(text)
    expect(events.map((e) => e.type)).toEqual(['step', 'done'])
    expect(rest).toBe('event: probe\ndata: {"type":"pro')
  })

  it('survives an event split across chunks and ignores malformed blocks', () => {
    const first = parseSse('data: {"type":"notice","mess')
    expect(first.events).toEqual([])
    const second = parseSse(first.rest + 'age":"switched"}\n\ndata: not json\n\n')
    expect(second.events).toEqual([{ type: 'notice', message: 'switched' }])
  })
})
