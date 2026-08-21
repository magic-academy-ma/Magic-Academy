import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('buildSimulationSocketUrl', () => {
  it('defaults to localhost:8000 and uses ws://', async () => {
    vi.resetModules()
    const { buildSimulationSocketUrl } = await import('./socket.js')
    expect(buildSimulationSocketUrl('sim-01')).toBe('ws://localhost:8000/v1/ws/simulations/sim-01')
  })

  it('converts VITE_API_URL http(s) to ws(s)', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.magic-academy.dev')
    vi.resetModules()
    const { buildSimulationSocketUrl } = await import('./socket.js')
    expect(buildSimulationSocketUrl('sim-02')).toBe('wss://api.magic-academy.dev/v1/ws/simulations/sim-02')
  })
})
