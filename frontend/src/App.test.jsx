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
function tickResult(overrides = {}) {
  return {
    previous_tick: 0,
    current_tick: 1,
    current_day: 1,
    status: 'COMPLETED',
    agent_results: [],
    ...overrides,
  }
}
async function setupSimulationWithAgents() {
  const fetchMock = createFetchMock()

  render(<App />)
  await login()
  await completeOnboarding()
  await screen.findByText('Agent 6명')

  return fetchMock
}

// User Persona 설정 옵션 (UserPersonaSetup이 workspace 진입과 동시에 조회한다).
const personaConfigData = {
  rule_version: 'mbti-big-five-v0.1',
  global_min: -50,
  global_max: 50,
  step: 5,
  mbti_rules: {
    ISTJ: {
      openness: { min: -45, default: -25, max: 5 },
      conscientiousness: { min: -15, default: 25, max: 45 },
      extraversion: { min: -45, default: -25, max: 5 },
      agreeableness: { min: -45, default: -20, max: 15 },
      emotional_stability: { min: -50, default: 0, max: 50 },
    },
  },
}

function response(body, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) })
}

// 여러 번 호출되는 엔드포인트(예: 재시도)를 순서대로 흘려보내고, 배열이 소진되면 마지막 항목을 반복한다.
function sequence(handlers) {
  let index = 0
  return () => {
    const handler = handlers[Math.min(index, handlers.length - 1)]
    index += 1
    return handler()
  }
}

// mockImplementationOnce 체인 대신 URL 기준으로 분기하는 공용 mock을 사용한다.
function createFetchMock({ login, createSimulation, agents: agentsHandlers } = {}) {
  const loginHandler = login ?? (() => response({ access_token: 'token', token_type: 'bearer', user }))
  const createSimHandler = createSimulation ?? (() => response(simulation, 201))
  const agentsHandler = agentsHandlers ? sequence(agentsHandlers) : () => response(agents)

  return vi.spyOn(globalThis, 'fetch').mockImplementation((url, options = {}) => {
    if (url.endsWith('/v1/auth/login')) return loginHandler()
    if (url.endsWith('/v1/simulations') && options.method === 'POST') return createSimHandler()
    if (url.endsWith('/agents')) return agentsHandler()
    if (url.includes('/user-persona/config')) return response({ data: personaConfigData })
    if (url.includes('/user-persona')) return response({}, 404) // 아직 미설정 (정상 상태)
    return response({}, 404)
  })
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

async function completeOnboarding() {
  await userEvent.click(await screen.findByRole('button', { name: '입학하기' }))
  await userEvent.click(await screen.findByRole('button', { name: '이 Persona로 시작하기 →' }))
  await userEvent.click(await screen.findByRole('button', { name: /시뮬레이션 시작/ }))
}

describe('Slice 0 UI', () => {
  it('logs in, enrolls, completes persona setup, and renders six API agents', async () => {
    createFetchMock()
    render(<App />)
    await login()
    expect(await screen.findByRole('heading', { name: /마법이 살아 숨쉬는/ })).toBeInTheDocument()
    await completeOnboarding()
    expect(await screen.findByText('Agent 6명')).toBeInTheDocument()
    expect(document.querySelectorAll('[data-agent-id]')).toHaveLength(6)
    await userEvent.click(screen.getByRole('button', { name: /아델/ }))
    expect(screen.getByRole('heading', { name: '아델' })).toBeInTheDocument()
    expect(screen.getByText('기숙사')).toBeInTheDocument()
  }, 10000)

  it('shows a disabled loading button while enrolling', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ access_token: 'token', token_type: 'bearer', user }))
      .mockImplementationOnce(() => new Promise(() => {}))

    render(<App />)
    await login()
    await userEvent.click(await screen.findByRole('button', { name: '입학하기' }))

    expect(screen.getByRole('button', { name: '입학 중...' })).toBeDisabled()
  })

  it('shows an inline error when enrollment fails', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ access_token: 'token', token_type: 'bearer', user }))
      .mockImplementationOnce(() => response({}, 500))

    render(<App />)
    await login()
    await userEvent.click(await screen.findByRole('button', { name: '입학하기' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.')
    expect(screen.getByRole('button', { name: '입학하기' })).toBeEnabled()
  })

  it('shows the basic 401 message', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => response({}, 401))
    render(<App />)
    await login()
    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요하거나 만료되었습니다.')
  })

  it('shows an empty-agent message', async () => {
    createFetchMock({ agents: [() => response([])] })
    render(<App />)
    await login()
    await completeOnboarding()
    expect(await screen.findByText('표시할 Agent가 없습니다.')).toBeInTheDocument()
  })

  it('keeps the created simulation and retries only the agent request', async () => {
    const fetchMock = createFetchMock({ agents: [() => response({}, 500), () => response(agents)] })

    render(<App />)
    await login()
    await completeOnboarding()

    expect(await screen.findByRole('heading', { name: 'Magic Academy Simulation' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.')
    await userEvent.click(screen.getByRole('button', { name: 'Agent 다시 불러오기' }))

    expect(await screen.findByText('Agent 6명')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/agents'))).toHaveLength(2)
    expect(fetchMock.mock.calls.filter(([url, options]) =>
      url.endsWith('/v1/simulations') && options?.method === 'POST'
    )).toHaveLength(1)
  })

  it('clears the previous user session state after an agent request returns 401', async () => {
    const nextUser = { ...user, id: '01900000-0000-7000-8000-000000000099', username: 'owner-b', display_name: 'Owner B' }
    createFetchMock({
      login: sequence([
        () => response({ access_token: 'token-a', token_type: 'bearer', user }),
        () => response({ access_token: 'token-b', token_type: 'bearer', user: nextUser }),
      ]),
      agents: [() => response({}, 401)],
    })

    render(<App />)
    await login()
    await userEvent.click(await screen.findByRole('button', { name: '입학하기' }))

    expect(await screen.findByRole('main')).toHaveClass('auth-shell')
    await login()

    expect(await screen.findByRole('heading', { name: /마법이 살아 숨쉬는/ })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Magic Academy Simulation' })).not.toBeInTheDocument()
    expect(document.querySelectorAll('[data-agent-id]')).toHaveLength(0)
  })
  it('shows loading state while a tick is running', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => new Promise(() => {})) // never resolves

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(screen.getByRole('button', { name: 'Tick 실행 중...' })).toBeDisabled()
  })

  it('renders a PROPOSED agent result on success', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response(tickResult({
      agent_results: [{
        agent_id: agents[0].id,
        agent_name: agents[0].name,
        runtime_status: 'PROPOSED',
        action_type: 'STUDY',
        utterance: '오늘도 열심히 공부하자',
        motivation_summary: '학업 성취 욕구가 높음',
        decision_explanation: { influencing_factors: [{ source: 'mood', description: '기분이 좋음', direction: 'positive' }] },
        retry_count: 0,
        failure_reason: null,
      }],
    })))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(await screen.findByText('STUDY')).toBeInTheDocument()
    expect(screen.getByText('“오늘도 열심히 공부하자”')).toBeInTheDocument()
    expect(screen.getByText('정상 진행')).toBeInTheDocument()
  })

  it('shows an empty agent-results message', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response(tickResult({ agent_results: [] })))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(await screen.findByText('이번 Tick에서 표시할 Agent 행동 결과가 없습니다.')).toBeInTheDocument()
  })

  it('renders a FALLBACK agent result with retry info', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response(tickResult({
      agent_results: [{
        agent_id: agents[0].id,
        agent_name: agents[0].name,
        runtime_status: 'FALLBACK',
        action_type: 'IDLE',
        utterance: null,
        motivation_summary: null,
        decision_explanation: null,
        retry_count: 3,
        failure_reason: 'LLM_TIMEOUT',
      }],
    })))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(await screen.findByText('재시도 실패 → Fallback 적용')).toBeInTheDocument()
    expect(screen.getByText('재시도 3회 실패 — 사유: LLM_TIMEOUT')).toBeInTheDocument()
  })

  it('renders relationship_deltas as delta badges on the relationship graph', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response(tickResult({
      relationship_deltas: [{
        effect_id: 'run:1:a:rel:TRUST_UP:b',
        rule_id: 'REL_TRUST_UP_MEDIUM',
        source_agent_id: agents[0].id,
        target_agent_id: agents[1].id,
        metric: 'trust',
        delta: 3,
        before: 0,
        after_preview: 3,
        reason: '대화 후 신뢰 상승',
      }],
    })))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(await screen.findByText('관계 변화')).toBeInTheDocument()
  })

  it('renders a SKIPPED agent result without action details', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response(tickResult({
      agent_results: [{
        agent_id: agents[0].id,
        agent_name: agents[0].name,
        runtime_status: 'SKIPPED',
        action_type: null,
        utterance: null,
        motivation_summary: null,
        decision_explanation: null,
        retry_count: 0,
        failure_reason: null,
      }],
    })))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(await screen.findByText('이번 Tick 미참여')).toBeInTheDocument()
    expect(screen.getByText('비활성 상태로 이번 Tick에서 행동하지 않았습니다.')).toBeInTheDocument()
    expect(screen.queryByText('IDLE')).not.toBeInTheDocument()
  })

  it('returns to the login screen with a notice on tick auth error', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response({ error: { code: 'UNAUTHORIZED', message: '로그인이 필요하거나 만료되었습니다.' } }, 401))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(await screen.findByRole('main')).toHaveClass('auth-shell')
    expect(screen.getByRole('alert')).toHaveTextContent('로그인이 필요하거나 만료되었습니다.')
  })

  it('shows a concurrent-tick message on TICK_ALREADY_RUNNING', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response({
      error: { code: 'TICK_ALREADY_RUNNING', message: '이미 진행 중인 Tick이 있습니다.' },
    }, 409))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 진행 중인 Tick이 있습니다')
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument()
  })
  it('does not treat a 409 with a different error code as TICK_ALREADY_RUNNING', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response({
      error: { code: 'SIMULATION_LOCKED', message: '시뮬레이션이 잠겨 있습니다.' },
    }, 409))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('시뮬레이션이 잠겨 있습니다.')
    expect(screen.queryByText('이미 진행 중인 Tick이 있습니다')).not.toBeInTheDocument()
  })

  it('sends the tick advance request without a request body', async () => {
    const fetchMock = await setupSimulationWithAgents()
    fetchMock.mockImplementationOnce(() => response(tickResult({ agent_results: [] })))

    await userEvent.click(screen.getByRole('button', { name: 'Tick 실행' }))
    await screen.findByText('이번 Tick에서 표시할 Agent 행동 결과가 없습니다.')

    const tickCall = fetchMock.mock.calls.find(([url]) => url.includes('/ticks/advance'))
    expect(tickCall[1]).not.toHaveProperty('body')
  })
})
