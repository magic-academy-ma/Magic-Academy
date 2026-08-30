import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSimulationWS } from './useSimulationWS.js'

class MockWebSocket {
  static instances = []

  constructor() {
    this.send = vi.fn()
    MockWebSocket.instances.push(this)
  }

  emit(message) {
    this.onmessage?.({ data: JSON.stringify(message) })
  }

  close() {}
}

beforeEach(() => {
  MockWebSocket.instances = []
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => vi.unstubAllGlobals())

describe('useSimulationWS', () => {
  it('keeps one event-log entry for repeated event content', () => {
    const { result } = renderHook(() => useSimulationWS('simulation-1', 'token'))
    const socket = MockWebSocket.instances[0]

    act(() => socket.emit({ type: 'EVENT_CREATED', data: { event_id: 'event-1', title: '통합마법학 개론', tick_number: 1 } }))
    act(() => socket.emit({ type: 'EVENT_CREATED', data: { event_id: 'event-2', title: '통합마법학 개론', tick_number: 2 } }))

    expect(result.current.eventLog).toHaveLength(1)
    expect(result.current.eventLog[0]).toMatchObject({ id: 'event-2', tick: 2 })
  })

  it('stores the action and resolved location from AGENT_ACTION_UPDATED', () => {
    const { result } = renderHook(() => useSimulationWS('simulation-1', 'token'))
    const socket = MockWebSocket.instances[0]
    const location = { id: 'location-1', code: 'classroom', name: '교실' }

    act(() => socket.emit({ type: 'AGENT_ACTION_UPDATED', data: { agent_id: 'agent-1', action_type: 'ATTEND_CLASS', location } }))

    expect(result.current.agentActions.get('agent-1')).toEqual({ action_type: 'ATTEND_CLASS', location })
  })
})
