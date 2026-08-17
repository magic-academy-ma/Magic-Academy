import { describe, expect, it } from 'vitest'
import { handleMockRequest } from './handlers.js'
import { mockAuthUser } from './fixtures/auth.js'
import { mockAgents } from './fixtures/agents.js'
import { mockSimulations } from './fixtures/simulations.js'

describe('handleMockRequest', () => {
  it('returns mock auth user on POST /v1/auth/login', async () => {
    const res = await handleMockRequest('/v1/auth/login', { method: 'POST' })
    expect(res).toEqual(mockAuthUser)
  })

  it('returns mock simulations on GET /v1/simulations', async () => {
    const res = await handleMockRequest('/v1/simulations', { method: 'GET' })
    expect(res).toEqual(mockSimulations)
  })

  it('returns mock agents on GET /v1/simulations/sim-001/agents', async () => {
    const res = await handleMockRequest('/v1/simulations/sim-001/agents', { method: 'GET' })
    expect(res).toEqual(mockAgents)
  })
})
