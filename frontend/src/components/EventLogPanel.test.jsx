import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import EventLogPanel from './EventLogPanel.jsx'

afterEach(cleanup)

describe('EventLogPanel', () => {
  it('passes the clicked event and selects its first agent', async () => {
    const onEventOpen = vi.fn()
    const onAgentSelect = vi.fn()
    const event = { id: 'event-1', event_type: 'MAGICAL_DISCOVERY', description: '마법 발견', involved_agents: ['a1', 'a2'], tick: 3 }
    render(<EventLogPanel eventLog={[event]} onEventOpen={onEventOpen} onAgentSelect={onAgentSelect} />)

    await userEvent.click(screen.getByRole('button', { name: /마법 발견/ }))

    expect(onEventOpen).toHaveBeenCalledWith(event)
    expect(onAgentSelect).toHaveBeenCalledWith('a1')
  })
})
