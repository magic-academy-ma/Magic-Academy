import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import RelationshipChangesPanel from './RelationshipChangesPanel.jsx'

afterEach(cleanup)

describe('RelationshipChangesPanel', () => {
  it('renders nothing when there are no updates', () => {
    const { container } = render(<RelationshipChangesPanel updates={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders source/target agents and formatted deltas', () => {
    render(<RelationshipChangesPanel updates={[{ relationship_id: 'relationship-01', source_agent_id: 'student-01', target_agent_id: 'student-02', changes: { affection: 5, tension: -1 } }]} />)
    expect(screen.getByText('Agent student-01 → student-02')).toBeInTheDocument()
    expect(screen.getByText('affection +5')).toBeInTheDocument()
    expect(screen.getByText('tension -1')).toBeInTheDocument()
  })
})
