import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'

const user = { id: '01900000-0000-7000-8000-000000000001', username: 'owner-a', display_name: 'Owner A', roles: ['USER'] }
const simulation = { id: '01900000-0000-7000-8000-000000000002', owner_id: user.id, name: 'Slice 0', status: 'ready', current_day: 1, current_tick: 0, magic_enabled: true, created_at: '2026-08-05T00:00:00Z' }
const names = ['에단', '아델', '레오', '리아', '카이', '세라']
const agents = ['professor-01', 'student-01', 'student-02', 'student-03', 'student-04', 'student-05'].map((key, index) => ({
  id: `01900000-0000-7000-8000-00000000001${index}`,
  fixture_key: key,
  fixture_version: key.startsWith('student') ? 'student-fixture-v0.2' : 'professor-fixture-v0.2',
  name: names[index], agent_type: key.startsWith('student') ? 'student' : 'professor', mbti_type: 'ISTJ',
  profile: { openness: 50, conscientiousness: 50, extraversion: 50, agreeableness: 50, emotional_stability: 50 },
  student_profile: key.startsWith('student') ? { grade: index, interest_field: '마법 연구' } : null,
  professor_profile: key.startsWith('student') ? null : { academic_rank: '통합 교수', specialty: '통합마법학과' },
  state: { hunger: 50, fatigue: 0, stress: 0, satisfaction: 50, mood: 0, current_action: null },
  location: { id: `01900000-0000-7000-8000-00000000002${index}`, code: key.startsWith('student') ? 'dormitory' : 'classroom', name: key.startsWith('student') ? '기숙사' : '교실' },
}))

function response(body, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) })
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

async function login() {
  await userEvent.type(screen.getByLabelText('아이디'), 'owner-a')
  await userEvent.type(screen.getByLabelText('비밀번호'), 'Slice0-password!')
  await userEvent.click(screen.getByRole('button', { name: '로그인' }))
}

describe('Slice 0 UI', () => {
  it('logs in, creates a simulation, and renders six API agents', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ access_token: 'token', token_type: 'bearer', user }))
      .mockImplementationOnce(() => response(simulation, 201))
      .mockImplementationOnce(() => response(agents))
    render(<App />)
    await login()
    expect(await screen.findByText('Owner A')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Simulation 생성' }))
    expect(await screen.findByText('Agent 6명')).toBeInTheDocument()
    expect(document.querySelectorAll('[data-agent-id]')).toHaveLength(6)
    await userEvent.click(screen.getByRole('button', { name: /아델/ }))
    expect(screen.getByRole('heading', { name: '아델' })).toBeInTheDocument()
    expect(screen.getByText('기숙사')).toBeInTheDocument()
  })

  it('shows the basic 401 message', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => response({}, 401))
    render(<App />)
    await login()
    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요하거나 만료되었습니다.')
  })

  it('shows an empty-agent message', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ access_token: 'token', token_type: 'bearer', user }))
      .mockImplementationOnce(() => response(simulation, 201))
      .mockImplementationOnce(() => response([]))
    render(<App />)
    await login()
    await userEvent.click(screen.getByRole('button', { name: 'Simulation 생성' }))
    expect(await screen.findByText('표시할 Agent가 없습니다.')).toBeInTheDocument()
  })

  it('keeps the created simulation and retries only the agent request', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ access_token: 'token', token_type: 'bearer', user }))
      .mockImplementationOnce(() => response(simulation, 201))
      .mockImplementationOnce(() => response({}, 500))
      .mockImplementationOnce(() => response(agents))

    render(<App />)
    await login()
    await userEvent.click(screen.getByRole('button', { name: 'Simulation 생성' }))

    expect(await screen.findByRole('heading', { name: simulation.name })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.')
    await userEvent.click(screen.getByRole('button', { name: 'Agent 다시 불러오기' }))

    expect(await screen.findByText('Agent 6명')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(fetchMock.mock.calls.filter(([url, options]) =>
      url.endsWith('/v1/simulations') && options?.method === 'POST'
    )).toHaveLength(1)
  })

  it('clears the previous user session state after an agent request returns 401', async () => {
    const nextUser = { ...user, id: '01900000-0000-7000-8000-000000000099', username: 'owner-b', display_name: 'Owner B' }
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ access_token: 'token-a', token_type: 'bearer', user }))
      .mockImplementationOnce(() => response(simulation, 201))
      .mockImplementationOnce(() => response({}, 401))
      .mockImplementationOnce(() => response({ access_token: 'token-b', token_type: 'bearer', user: nextUser }))

    render(<App />)
    await login()
    await userEvent.click(document.querySelector('.create-panel button'))

    expect(await screen.findByRole('main')).toHaveClass('auth-shell')
    await login()

    expect(await screen.findByText('Owner B')).toBeInTheDocument()
    expect(document.querySelector('.create-panel')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: simulation.name })).not.toBeInTheDocument()
    expect(document.querySelectorAll('[data-agent-id]')).toHaveLength(0)
  })
})
