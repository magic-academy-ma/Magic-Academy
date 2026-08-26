import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import EventFeed from './EventFeed.jsx'

afterEach(cleanup)

describe('EventFeed', () => {
  it('renders nothing when there are no events', () => {
    const { container } = render(<EventFeed events={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders event type, title, and location', () => {
    render(<EventFeed events={[{ event_id: 'event-100', event_type: 'CLASS', title: '변환 마법 수업', location: 'library' }]} />)
    expect(screen.getByText('CLASS')).toBeInTheDocument()
    expect(screen.getByText('변환 마법 수업')).toBeInTheDocument()
    expect(screen.getByText('@ library')).toBeInTheDocument()
  })

  it('marks RANDOM_INCIDENT events with the special class', () => {
    render(<EventFeed events={[{ event_id: 'event-101', event_type: 'RANDOM_INCIDENT', title: '마법 실험실 폭발 사고' }]} />)
    expect(screen.getByText('마법 실험실 폭발 사고').closest('li')).toHaveClass('event-item-special')
  })
})
