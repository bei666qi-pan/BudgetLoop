import { describe, it, expect } from 'vitest'
import {
  formatTokens,
  formatCost,
  formatDurationMs,
  formatDurationSec,
  formatTime,
  formatDateTime,
  percent,
} from '../lib/format'

// ── formatTokens ──

describe('formatTokens', () => {
  it('returns "—" for null', () => {
    expect(formatTokens(null)).toBe('—')
  })

  it('returns "—" for undefined', () => {
    expect(formatTokens(undefined)).toBe('—')
  })

  it('returns string number for 0', () => {
    expect(formatTokens(0)).toBe('0')
  })

  it('returns string number for values < 1000', () => {
    expect(formatTokens(999)).toBe('999')
    expect(formatTokens(1)).toBe('1')
    expect(formatTokens(500)).toBe('500')
  })

  it('formats 1000 as "1.0k"', () => {
    expect(formatTokens(1000)).toBe('1.0k')
  })

  it('formats values between 1000 and 1M as "X.Xk"', () => {
    expect(formatTokens(1500)).toBe('1.5k')
    expect(formatTokens(999999)).toBe('1000.0k')
  })

  it('formats 1000000 as "1.00M"', () => {
    expect(formatTokens(1000000)).toBe('1.00M')
  })

  it('formats large values as "X.XXM"', () => {
    expect(formatTokens(2500000)).toBe('2.50M')
    expect(formatTokens(999999999)).toBe('1000.00M')
  })
})

// ── formatCost ──

describe('formatCost', () => {
  it('returns default nullText for null', () => {
    expect(formatCost(null)).toBe('价格未配置')
  })

  it('returns default nullText for undefined', () => {
    expect(formatCost(undefined)).toBe('价格未配置')
  })

  it('returns custom nullText when provided', () => {
    expect(formatCost(null, 'N/A')).toBe('N/A')
  })

  it('formats 0 as "$0.00"', () => {
    expect(formatCost(0)).toBe('$0.00')
  })

  it('formats values < 0.01 with 4 decimal places', () => {
    expect(formatCost(0.001)).toBe('$0.0010')
    expect(formatCost(0.0099)).toBe('$0.0099')
  })

  it('formats values >= 0.01 with 2 decimal places', () => {
    expect(formatCost(0.01)).toBe('$0.01')
    expect(formatCost(1.5)).toBe('$1.50')
    expect(formatCost(100)).toBe('$100.00')
  })
})

// ── formatDurationMs ──

describe('formatDurationMs', () => {
  it('returns "—" for null', () => {
    expect(formatDurationMs(null)).toBe('—')
  })

  it('returns "—" for undefined', () => {
    expect(formatDurationMs(undefined)).toBe('—')
  })

  it('returns "0s" for 0', () => {
    expect(formatDurationMs(0)).toBe('0s')
  })

  it('returns "45s" for 45000', () => {
    expect(formatDurationMs(45000)).toBe('45s')
  })

  it('returns "1m30s" for 90000', () => {
    expect(formatDurationMs(90000)).toBe('1m30s')
  })

  it('returns "1h0m" for 3600000', () => {
    expect(formatDurationMs(3600000)).toBe('1h0m')
  })

  it('returns "1h1m" for 3661000', () => {
    expect(formatDurationMs(3661000)).toBe('1h1m')
  })

  it('treats negative values as 0', () => {
    expect(formatDurationMs(-5000)).toBe('0s')
    expect(formatDurationMs(-100000)).toBe('0s')
  })
})

// ── formatDurationSec ──

describe('formatDurationSec', () => {
  it('returns "—" for null', () => {
    expect(formatDurationSec(null)).toBe('—')
  })

  it('returns "0s" for 0 seconds', () => {
    expect(formatDurationSec(0)).toBe('0s')
  })

  it('returns seconds-only for values under 60', () => {
    expect(formatDurationSec(45)).toBe('45s')
  })

  it('returns minutes and seconds for values under 3600', () => {
    expect(formatDurationSec(90)).toBe('1m30s')
    expect(formatDurationSec(120)).toBe('2m0s')
  })

  it('returns hours and minutes for values >= 3600', () => {
    expect(formatDurationSec(3600)).toBe('1h0m')
    expect(formatDurationSec(3661)).toBe('1h1m')
    expect(formatDurationSec(7200)).toBe('2h0m')
  })

  it('treats negative values as 0', () => {
    expect(formatDurationSec(-10)).toBe('0s')
  })
})

// ── formatTime ──

describe('formatTime', () => {
  it('returns "—" for null', () => {
    expect(formatTime(null)).toBe('—')
  })

  it('returns "—" for undefined', () => {
    expect(formatTime(undefined)).toBe('—')
  })

  it('returns "—" for empty string', () => {
    expect(formatTime('')).toBe('—')
  })

  it('formats a valid ISO string as HH:MM:SS', () => {
    // Use a fixed date to avoid timezone issues
    const result = formatTime('2024-01-15T14:30:45Z')
    // Should contain two colons and be a time format
    expect(result).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })

  it('returns original string for invalid date', () => {
    expect(formatTime('not-a-date')).toBe('not-a-date')
  })
})

// ── formatDateTime ──

describe('formatDateTime', () => {
  it('returns "—" for null', () => {
    expect(formatDateTime(null)).toBe('—')
  })

  it('returns "—" for undefined', () => {
    expect(formatDateTime(undefined)).toBe('—')
  })

  it('returns "—" for empty string', () => {
    expect(formatDateTime('')).toBe('—')
  })

  it('formats a valid ISO string as a locale string', () => {
    const result = formatDateTime('2024-01-15T14:30:45Z')
    // Should be a non-empty string longer than just time
    expect(result.length).toBeGreaterThan(8)
    expect(result).not.toBe('—')
  })

  it('returns original string for invalid date', () => {
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
  })
})

// ── percent ──

describe('percent', () => {
  it('returns 50 for 50/100', () => {
    expect(percent(50, 100)).toBe(50)
  })

  it('returns 0 for 0/max', () => {
    expect(percent(0, 100)).toBe(0)
  })

  it('returns 100 for max/max', () => {
    expect(percent(100, 100)).toBe(100)
  })

  it('caps over 100% at 100', () => {
    expect(percent(150, 100)).toBe(100)
  })

  it('returns null when denominator is 0', () => {
    expect(percent(50, 0)).toBeNull()
  })

  it('returns null when denominator is negative', () => {
    expect(percent(50, -1)).toBeNull()
  })
})
