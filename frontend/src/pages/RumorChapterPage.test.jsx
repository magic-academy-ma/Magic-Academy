import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import RumorChapterPage from './RumorChapterPage.jsx';
import MainPage from './MainPage.jsx';
import { apiRequest } from '../api/client.js';
vi.mock('../api/client.js', () => ({ apiRequest: vi.fn() }));
vi.mock('../components/InspectorPanel.jsx', () => ({ default: () => <div>학생 상태</div> }));
vi.mock('../components/RelationshipModal.jsx', () => ({ default: () => <div>관계 그래프</div> }));
const auth = { access_token: 'test' };
const base = {
  id: 'run-1', simulation_id: 'sim-1', revision: 0, busy: false, current_tick: 0, current_round: 1,
  status: 'in_progress', needs_intervention: false, inquiries_remaining: 3,
  agents: [{ id: 's1', name: '아델', agent_type: 'student' }, { id: 'p1', name: '에단', agent_type: 'professor' }],
  observations: [], investigations: [], history: [], statements: [], information: [], interventions: [], achievements: [],
  choices: [{ value: 'WATCH', label: '지켜보기' }, { value: 'REQUEST_TESTIMONY', label: '증언 요청' }],
  topics: [{ value: 'RUMOR', label: '들은 소문' }, { value: 'VERIFY', label: '사실 확인' }],
};
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('메인 화면에서 CHAPTER 1로 진입한다', async () => {
  const onRumorChapter = vi.fn();
  render(<MainPage displayName="조정관" onRumorChapter={onRumorChapter} />);
  await userEvent.click(screen.getByRole('button', { name: '거짓 소문의 확산을 막아라' }));
  expect(onRumorChapter).toHaveBeenCalledOnce();
});

it('도입 → 시작 → 관찰 → 조사 → 요청 → 진행 → 엔딩까지 연결한다', async () => {
  let current = null;
  const calls = [];
  apiRequest.mockImplementation(async (path, options = {}) => {
    if (path.includes('/simulations/')) return base.agents;
    if (path.endsWith('/current')) return { data: current };
    const body = options.body ? JSON.parse(options.body) : null;
    if (body) calls.push({ path, body });
    if (path === '/v1/challenges/rumor') current = structuredClone(base);
    else if (path.endsWith('/advance')) {
      const tick = current.current_tick + 1;
      current = { ...current, current_tick: tick, needs_intervention: tick === 1, revision: current.revision + 1,
        observations: [{ actor: 's1', tick, action: 'TALK', status: 'PROPOSED' }] };
      if (tick === 2) current = { ...current, current_tick: 9, status: 'completed', ending: 'MISUNDERSTANDING', achievements: [{ id: 'CHAPTER1_CLEAR', label: '챌린지 1 클리어' }] };
    } else if (path.endsWith('/investigate')) {
      current = { ...current, revision: current.revision + 1, inquiries_remaining: 2,
        statements: [{ actor: 's1', tick: 1, text: '금지 마법 소문' }], information: [{ id: 'R0', text: '금지 마법 소문', confirmed: false }] };
    } else if (path.endsWith('/intervene')) current = { ...current, revision: current.revision + 1, needs_intervention: false,
      interventions: [{ tick: 1, choice: body.choice, target: body.target }] };
    return { data: current };
  });
  render(<RumorChapterPage auth={auth} onBack={vi.fn()} />);
  await userEvent.click(await screen.findByRole('button', { name: 'CHAPTER 1 시작' }));
  await userEvent.click(await screen.findByRole('button', { name: '다음 틱 관찰' }));
  await userEvent.click(await screen.findByRole('button', { name: '조사·대화하기' }));
  expect(await screen.findByText(/들은 진술 · 미확인/)).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText('개입 방식'), 'REQUEST_TESTIMONY');
  await userEvent.click(screen.getByRole('button', { name: '개입 제출' }));
  const request = calls.find(c => c.path.endsWith('/intervene'));
  expect(request.body).toMatchObject({ choice: 'REQUEST_TESTIMONY', target: 's1', information_id: 'R0', expected_revision: 2 });
  expect(request.body.request_id).toBeTruthy();
  await userEvent.click(await screen.findByRole('button', { name: '다음 틱 관찰' }));
  expect(await screen.findByText('챕터 종료')).toBeInTheDocument();
  expect(screen.getByText('챌린지 1 클리어')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '개입 제출' })).not.toBeInTheDocument();
});

it('새로고침 후 서버의 진행 위치와 확인 기록을 이어간다', async () => {
  const current = { ...base, revision: 4, current_tick: 4, current_round: 2, needs_intervention: true,
    information: [{ id: 'F', text: '확인된 보호마법 실습', confirmed: true }] };
  apiRequest.mockImplementation(async path => path.endsWith('/current') ? { data: current } : base.agents);
  const first = render(<RumorChapterPage auth={auth} onBack={vi.fn()} />);
  expect(await screen.findByText('2라운드 · 4 / 9틱')).toBeInTheDocument();
  first.unmount();
  render(<RumorChapterPage auth={auth} onBack={vi.fn()} />);
  expect(await screen.findByText(/확인된 사실 — 확인된 보호마법 실습/)).toBeInTheDocument();
  expect(screen.getByText('2라운드 · 4 / 9틱')).toBeInTheDocument();
  expect(apiRequest.mock.calls.every(([, options]) => !options?.method)).toBe(true);
});

it('실행 중 명령이 있으면 진행 버튼을 잠근다', async () => {
  apiRequest.mockImplementation(async path => path.endsWith('/current') ? { data: { ...base, busy: true } } : base.agents);
  render(<RumorChapterPage auth={auth} onBack={vi.fn()} />);
  await waitFor(() => expect(screen.getByRole('button', { name: '다음 틱 관찰' })).toBeDisabled());
});

it('남아 있는 실행 기록을 복구하고 진행을 바꾸지 않은 채 이어간다', async () => {
  apiRequest.mockImplementation(async (path, options = {}) => {
    if (path.endsWith('/current')) return { data: { ...base, busy: true } };
    if (path.endsWith('/recover')) {
      expect(JSON.parse(options.body).expected_revision).toBe(0);
      return { data: { ...base, busy: false } };
    }
    return base.agents;
  });
  render(<RumorChapterPage auth={auth} onBack={vi.fn()} />);
  await userEvent.click(await screen.findByRole('button', { name: '중단된 실행 복구' }));
  await waitFor(() => expect(screen.getByRole('button', { name: '다음 틱 관찰' })).not.toBeDisabled());
  expect(screen.getByText('1라운드 · 0 / 9틱')).toBeInTheDocument();
  expect(apiRequest.mock.calls.filter(([path]) => path.endsWith('/advance'))).toHaveLength(0);
});
