import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSimulationSocket } from './useSimulationSocket.js'

class MockWebSocket {
  static instances = []
  constructor(url) {
    this.url = url
    this.readyState = 0
    this.onopen = null
    this.onmessage = null
    this.onclose = null
    this.onerror = null
    MockWebSocket.instances.push(this)
  }
  open() {
    this.readyState = 1
    this.onopen?.()
  }
  emit(message) {
    this.onmessage?.({ data: JSON.stringify(message) })
  }
  close() {
    this.readyState = 3
    this.onclose?.()
  }
}

function latestSocket() {
  return MockWebSocket.instances[MockWebSocket.instances.length - 1]
}

beforeEach(() => {
  MockWebSocket.instances = []
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('useSimulationSocket', () => {
  it('does not connect when wsUrl is null', () => {
    renderHook(() => useSimulationSocket({ wsUrl: null }))
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('connects and marks connected on open', async () => {
    const { result } = renderHook(() => useSimulationSocket({ wsUrl: 'ws://test/sim' }))
    expect(result.current.connected).toBe(false)
    act(() => latestSocket().open())
    await waitFor(() => expect(result.current.connected).toBe(true))
  })

  it('updates tick and calls onTickUpdated once per new tick_number', () => {
    const onTickUpdated = vi.fn()
    renderHook(() => useSimulationSocket({ wsUrl: 'ws://test/sim', onTickUpdated }))
    act(() => latestSocket().open())
    const tickData = { simulation_id: 'sim-01', current_day: 1, tick_number: 1 }
    act(() => latestSocket().emit({ type: 'TICK_UPDATED', data: tickData }))
    act(() => latestSocket().emit({ type: 'TICK_UPDATED', data: tickData }))
    expect(onTickUpdated).toHaveBeenCalledTimes(1)
    expect(onTickUpdated).toHaveBeenCalledWith(tickData)
  })

  it('calls onAgentAction on AGENT_ACTION_UPDATED', () => {
    const onAgentAction = vi.fn()
    renderHook(() => useSimulationSocket({ wsUrl: 'ws://test/sim', onAgentAction }))
    act(() => latestSocket().open())
    const data = { agent_id: 'student-01', action: 'MOVE', location: 'library' }
    act(() => latestSocket().emit({ type: 'AGENT_ACTION_UPDATED', data }))
    expect(onAgentAction).toHaveBeenCalledWith(data)
  })

  it('deduplicates EVENT_CREATED by event_id', () => {
    const { result } = renderHook(() => useSimulationSocket({ wsUrl: 'ws://test/sim' }))
    act(() => latestSocket().open())
    const eventData = { event_id: 'event-100', event_type: 'RANDOM_INCIDENT', title: '사건' }
    act(() => latestSocket().emit({ type: 'EVENT_CREATED', data: eventData }))
    act(() => latestSocket().emit({ type: 'EVENT_CREATED', data: eventData }))
    expect(result.current.events).toHaveLength(1)
  })

  it('accumulates RELATIONSHIP_UPDATED messages', () => {
    const { result } = renderHook(() => useSimulationSocket({ wsUrl: 'ws://test/sim' }))
    act(() => latestSocket().open())
    const data = { relationship_id: 'relationship-01', source_agent_id: 'a', target_agent_id: 'b', changes: { trust: 3 } }
    act(() => latestSocket().emit({ type: 'RELATIONSHIP_UPDATED', data }))
    expect(result.current.relationshipUpdates).toEqual([data])
  })

  it('reconnects after close and calls onReconnect on the next open', () => {
    vi.useFakeTimers()
    const onReconnect = vi.fn()
    renderHook(() => useSimulationSocket({ wsUrl: 'ws://test/sim', onReconnect }))
    act(() => latestSocket().open())
    act(() => latestSocket().close())
    expect(MockWebSocket.instances).toHaveLength(1)
    act(() => vi.advanceTimersByTime(1000))
    expect(MockWebSocket.instances).toHaveLength(2)
    act(() => latestSocket().open())
    expect(onReconnect).toHaveBeenCalledTimes(1)
  })
})
