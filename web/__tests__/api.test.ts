import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  ApiError,
  idempotencyKey,
  apiFetch,
  checkHealth,
  downloadFile,
} from '../lib/api'

// ── ApiError ──

describe('ApiError', () => {
  it('creates with message and status', () => {
    const err = new ApiError('Not Found', 404)
    expect(err.message).toBe('Not Found')
    expect(err.status).toBe(404)
  })

  it('isUnreachable is true when status is null', () => {
    const err = new ApiError('Network error', null)
    expect(err.isUnreachable).toBe(true)
  })

  it('isUnreachable is false when status is 404', () => {
    const err = new ApiError('Not Found', 404)
    expect(err.isUnreachable).toBe(false)
  })

  it('is an instance of Error', () => {
    const err = new ApiError('test')
    expect(err).toBeInstanceOf(Error)
  })

  it('has name "ApiError"', () => {
    const err = new ApiError('test')
    expect(err.name).toBe('ApiError')
  })
})

// ── idempotencyKey ──

describe('idempotencyKey', () => {
  it('returns a string', () => {
    const key = idempotencyKey()
    expect(typeof key).toBe('string')
    expect(key.length).toBeGreaterThan(0)
  })

  it('returns different values on consecutive calls', () => {
    const key1 = idempotencyKey()
    const key2 = idempotencyKey()
    expect(key1).not.toBe(key2)
  })
})

// ── apiFetch ──

describe('apiFetch', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns parsed JSON on successful GET', async () => {
    const mockData = { id: 1, name: 'test' }
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockData),
    })

    const result = await apiFetch('/api/tasks')
    expect(result).toEqual(mockData)
  })

  it('returns undefined on 204 response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    })

    const result = await apiFetch('/api/something')
    expect(result).toBeUndefined()
  })

  it('throws ApiError with status on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve('Not Found'),
    })

    await expect(apiFetch('/api/missing')).rejects.toThrow(ApiError)
    await expect(apiFetch('/api/missing')).rejects.toMatchObject({ status: 404 })
  })

  it('throws ApiError with null status on network error (isUnreachable)', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Connection refused'))

    await expect(apiFetch('/api/tasks')).rejects.toThrow(ApiError)
    try {
      await apiFetch('/api/tasks')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect((e as ApiError).isUnreachable).toBe(true)
    }
  })

  it('does not expose an Authorization header from the browser', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })

    await apiFetch('/api/tasks')

    const callArgs = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    const init = callArgs[1] as RequestInit
    expect(new Headers(init.headers).has('Authorization')).toBe(false)
  })

  it('includes Content-Type header', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })

    await apiFetch('/api/tasks')

    const callArgs = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    const init = callArgs[1] as RequestInit
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
  })

  it('merges custom headers', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })

    await apiFetch('/api/tasks', {
      headers: { 'X-Custom': 'value' },
    })

    const callArgs = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    const init = callArgs[1] as RequestInit
    expect(new Headers(init.headers).get('X-Custom')).toBe('value')
  })

  it('includes no-store cache', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    })

    await apiFetch('/api/tasks')

    const callArgs = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    const init = callArgs[1] as RequestInit
    expect(init.cache).toBe('no-store')
  })
})

// ── checkHealth ──

describe('checkHealth', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns true on 200', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true })
    const result = await checkHealth()
    expect(result).toBe(true)
  })

  it('returns false on 404', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false })
    const result = await checkHealth()
    expect(result).toBe(false)
  })

  it('returns false on network error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await checkHealth()
    expect(result).toBe(false)
  })
})

// ── downloadFile ──

describe('downloadFile', () => {
  let createObjectURLSpy: ReturnType<typeof vi.fn>
  let revokeObjectURLSpy: ReturnType<typeof vi.fn>
  let createElementSpy: ReturnType<typeof vi.fn>
  let appendChildSpy: ReturnType<typeof vi.fn>
  let clickSpy: ReturnType<typeof vi.fn>
  let removeSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.restoreAllMocks()

    createObjectURLSpy = vi.fn().mockReturnValue('blob:test')
    revokeObjectURLSpy = vi.fn()
    clickSpy = vi.fn()
    removeSpy = vi.fn()
    appendChildSpy = vi.fn()

    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: createObjectURLSpy,
      revokeObjectURL: revokeObjectURLSpy,
    })

    createElementSpy = vi.fn().mockReturnValue({
      href: '',
      download: '',
      click: clickSpy,
      remove: removeSpy,
    })

    vi.stubGlobal('document', {
      ...document,
      createElement: createElementSpy,
      body: { ...document.body, appendChild: appendChildSpy },
    })
  })

  it('creates blob URL and triggers download on success', async () => {
    const blob = new Blob(['test'])
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: () => Promise.resolve(blob),
    })

    await downloadFile('/api/report/export', 'report.csv')

    expect(createObjectURLSpy).toHaveBeenCalledWith(blob)
    expect(createElementSpy).toHaveBeenCalledWith('a')
    expect(clickSpy).toHaveBeenCalled()
    expect(removeSpy).toHaveBeenCalled()
    expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:test')
  })

  it('sets download attribute on anchor', async () => {
    const blob = new Blob(['test'])
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      blob: () => Promise.resolve(blob),
    })

    await downloadFile('/api/report/export', 'report.csv')

    const anchor = createElementSpy.mock.results[0].value
    expect(anchor.download).toBe('report.csv')
    expect(anchor.href).toBe('blob:test')
  })

  it('throws ApiError on non-ok response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Server Error'),
    })

    await expect(downloadFile('/api/report/export', 'report.csv')).rejects.toThrow(ApiError)
  })

  it('throws ApiError on network error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network down'))

    await expect(downloadFile('/api/report/export', 'report.csv')).rejects.toThrow(ApiError)
  })
})
