import { describe, expect, it } from 'vitest'
import { handleMockRequest } from './handlers.js'
import { mockAuthUser } from './fixtures/auth.js'
import { mockAgents } from './fixtures/agents.js'
import { mockSimulations } from './fixtures/simulations.js'

describe('handleMockRequest', () => {
  it('returns mock auth user on POST /v1/auth/login', async () => {
    const res = await handleMockRequest('/v1/auth/login', { method: 'POST' })
    expect(res).toEqual(mockAuthUser)
    expect(res.user.id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i)
    expect(res.user.roles).toEqual(['ADMIN'])
  })

  it('returns a UserResponse on POST /v1/auth/register', async () => {
    const res = await handleMockRequest('/v1/auth/register', { method: 'POST' })
    expect(res).toEqual(mockAuthUser.user)
  })

  it('returns mock simulations on GET /v1/simulations', async () => {
    const res = await handleMockRequest('/v1/simulations', { method: 'GET' })
    expect(res).toEqual({
      data: mockSimulations,
      meta: { next_cursor: null, has_more: false },
    })
  })

  it('returns the saved Simulation on POST /v1/simulations/:id/save', async () => {
    const res = await handleMockRequest('/v1/simulations/sim-001/save', { method: 'POST' })

    expect(res).toEqual({
      data: expect.objectContaining({
        id: 'sim-001',
        status: 'PAUSED',
        saved_at: expect.any(String),
      }),
    })
  })

  it('returns the restored Simulation and Persona on POST /v1/simulations/:id/restore', async () => {
    const res = await handleMockRequest('/v1/simulations/sim-001/restore', {
      method: 'POST',
      body: '{}',
    })

    expect(res).toEqual({
      data: expect.objectContaining({
        id: 'sim-001',
        name: expect.any(String),
        status: 'RUNNING',
        updated_at: expect.any(String),
        user_persona: {
          agent_id: expect.any(String),
          status: 'APPLIED',
          locked: true,
        },
      }),
    })
  })

  it('returns mock agents on GET /v1/simulations/sim-001/agents', async () => {
    const res = await handleMockRequest('/v1/simulations/sim-001/agents', { method: 'GET' })
    expect(res).toEqual(mockAgents)
    expect(res).toHaveLength(6)
    expect(res.every((agent) => agent.agent_type && agent.mbti_type && agent.profile && agent.state && agent.location)).toBe(true)
  })

  it('returns a SimulationResponse on POST /v1/simulations', async () => {
    const res = await handleMockRequest('/v1/simulations', {
      method: 'POST',
      body: JSON.stringify({ name: 'Mock 통합 테스트' }),
    })
    expect(res).toEqual(expect.objectContaining({
      id: expect.stringMatching(/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i),
      owner_id: mockAuthUser.user.id,
      name: 'Mock 통합 테스트',
      status: expect.any(String),
      current_day: expect.any(Number),
      current_tick: expect.any(Number),
      magic_enabled: expect.any(Boolean),
      created_at: expect.any(String),
    }))
    expect(res).not.toHaveProperty('total_agents')
  })
})
