import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { eventMeta, CATEGORY_STYLE, approvalIdOf, fetchEvents } from '../lib/events'

// ── CATEGORY_STYLE ──

describe('CATEGORY_STYLE', () => {
  const categories = [
    'plan', 'execute', 'tool', 'feedback', 'progress',
    'correction', 'approval', 'budget', 'message', 'warning', 'final',
  ] as const

  it('has all 11 categories defined', () => {
    expect(Object.keys(CATEGORY_STYLE)).toHaveLength(11)
  })

  it.each(categories)('category "%s" has dot, badge, and label properties', (cat) => {
    const style = CATEGORY_STYLE[cat]
    expect(style).toBeDefined()
    expect(style).toHaveProperty('dot')
    expect(style).toHaveProperty('badge')
    expect(style).toHaveProperty('label')
    expect(typeof style.dot).toBe('string')
    expect(typeof style.badge).toBe('string')
    expect(typeof style.label).toBe('string')
  })

  it('labels are in Chinese', () => {
    const labels = Object.values(CATEGORY_STYLE).map((s) => s.label)
    expect(labels).toEqual([
      '计划', '执行', '工具调用', '反馈', '进展评估',
      '修正', '审批', '预算', '消息', '警告', '最终结果',
    ])
  })
})

// ── eventMeta ──

describe('eventMeta', () => {
  const knownTypes = [
    'run_started', 'state_changed', 'phase_changed',
    'iteration_started', 'iteration_finished',
    'llm_call', 'tool_call', 'test_result',
    'progress_scored', 'budget_updated', 'budget_reallocated',
    'pressure_changed', 'strategy_switched', 'rollback',
    'approval_requested', 'approval_decided',
    'checkpoint_created', 'agent_message', 'warning', 'run_finished',
  ]

  it.each(knownTypes)('"%s" returns correct category', (type) => {
    const meta = eventMeta(type)
    expect(meta).toBeDefined()
    expect(meta).toHaveProperty('category')
    expect(meta).toHaveProperty('label')
    expect(meta).toHaveProperty('icon')
  })

  it('returns all 20 known event types with correct mapping', () => {
    const results = knownTypes.map((t) => ({ type: t, meta: eventMeta(t) }))
    expect(results).toHaveLength(20)
    results.forEach(({ type, meta }) => {
      expect(meta.category).toBeTruthy()
      expect(meta.label).toBeTruthy()
      expect(meta.icon).toBeTruthy()
    })
  })

  it('run_started has category "plan"', () => {
    expect(eventMeta('run_started').category).toBe('plan')
  })

  it('llm_call has category "execute"', () => {
    expect(eventMeta('llm_call').category).toBe('execute')
  })

  it('tool_call has category "tool"', () => {
    expect(eventMeta('tool_call').category).toBe('tool')
  })

  it('run_finished has category "final"', () => {
    expect(eventMeta('run_finished').category).toBe('final')
  })

  it('unknown event type defaults to "message" category', () => {
    const meta = eventMeta('unknown_event_type')
    expect(meta.category).toBe('message')
    expect(meta.label).toBe('unknown_event_type')
    expect(meta.icon).toBeTruthy()
    expect(typeof meta.icon).not.toBe('string')
  })

  it('all EVENT_META entries have label and icon', () => {
    // Test a sampling from each category
    const samples = [
      'run_started', 'llm_call', 'tool_call', 'test_result',
      'progress_scored', 'budget_updated', 'approval_requested',
      'checkpoint_created', 'agent_message', 'warning',
    ]
    samples.forEach((type) => {
      const meta = eventMeta(type)
      expect(meta.label).toBeTruthy()
      expect(meta.icon).toBeTruthy()
    })
  })
})

// ── approvalIdOf ──

describe('approvalIdOf', () => {
  it('returns string from approval_id field', () => {
    const payload = { approval_id: 'app-123' }
    expect(approvalIdOf(payload)).toBe('app-123')
  })

  it('falls back to id field when no approval_id', () => {
    const payload = { id: 'id-456' }
    expect(approvalIdOf(payload)).toBe('id-456')
  })

  it('returns null for non-string value', () => {
    const payload = { approval_id: 123 }
    expect(approvalIdOf(payload)).toBeNull()
  })

  it('returns null when both fields missing', () => {
    const payload = { other: 'value' }
    expect(approvalIdOf(payload)).toBeNull()
  })

  it('returns null for empty payload', () => {
    expect(approvalIdOf({})).toBeNull()
  })

  it('prefers approval_id over id when both present', () => {
    const payload = { approval_id: 'app-789', id: 'id-000' }
    expect(approvalIdOf(payload)).toBe('app-789')
  })
})

// ── fetchEvents ──

describe('fetchEvents', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns parsed events on successful response', async () => {
    const mockEvents = {
      events: [
        { seq: 1, type: 'run_started', payload: {}, created_at: '2024-01-01T00:00:00Z' },
        { seq: 2, type: 'llm_call', payload: {}, created_at: '2024-01-01T00:01:00Z' },
      ],
    }
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockEvents),
    })

    const result = await fetchEvents('run-1', 0)
    expect(result).toEqual(mockEvents)
    expect(result.events).toHaveLength(2)
  })

  it('returns empty events array on error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    })

    const result = await fetchEvents('run-1', 0)
    expect(result).toEqual({ events: [] })
  })

  it('constructs URL with correct run_id and after_seq', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ events: [] }),
    })

    await fetchEvents('run-42', 100)
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toContain('/api/runs/run-42/events')
    expect(url).toContain('after_seq=100')
  })

  it('leaves Authorization to the same-origin server proxy', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ events: [] }),
    })

    await fetchEvents('run-1', 0)
    const init = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit
    expect(init.headers).not.toHaveProperty('Authorization')
  })
})
