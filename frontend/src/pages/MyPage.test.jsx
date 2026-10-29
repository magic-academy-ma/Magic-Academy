import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import MyPage from './MyPage.jsx';

const auth = { access_token: 'token' };
const simulation = {
  id: 'sim-01',
  name: '첫 번째 시뮬레이션',
  status: 'PAUSED',
  current_day: 3,
  current_tick: 7,
  updated_at: '2026-08-27T12:00:00Z',
};

function response(body, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('MyPage', () => {
  it('{data, meta} 목록 응답을 파싱한다', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({
      data: [simulation],
      meta: { next_cursor: null, has_more: false },
    }));

    render(<MyPage auth={auth} onBack={vi.fn()} onRestore={vi.fn()} />);

    expect(screen.getByText('목록을 불러오는 중...')).toBeInTheDocument();
    expect(await screen.findByText('첫 번째 시뮬레이션')).toBeInTheDocument();
  });

  it('빈 목록을 표시한다', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({
      data: [],
      meta: { next_cursor: null, has_more: false },
    }));

    render(<MyPage auth={auth} onBack={vi.fn()} onRestore={vi.fn()} />);

    expect(await screen.findByText('저장된 시뮬레이션이 없습니다.')).toBeInTheDocument();
  });

  it('목록 조회 실패 오류를 표시한다', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({}, 500));

    render(<MyPage auth={auth} onBack={vi.fn()} onRestore={vi.fn()} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.');
  });

  it('restore 응답의 data로 onRestore를 호출한다', async () => {
    const restoredSimulation = {
      ...simulation,
      status: 'RUNNING',
      user_persona: { agent_id: 'agent-01', status: 'APPLIED', locked: true },
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ data: [simulation], meta: { next_cursor: null, has_more: false } }))
      .mockImplementationOnce(() => response({ data: restoredSimulation }));
    const onRestore = vi.fn();

    render(<MyPage auth={auth} onBack={vi.fn()} onRestore={onRestore} />);
    await userEvent.click(await screen.findByRole('button', { name: '불러오기' }));

    expect(fetchMock).toHaveBeenLastCalledWith(
      'http://localhost:8000/v1/simulations/sim-01/restore',
      expect.objectContaining({ method: 'POST', body: '{}' }),
    );
    expect(onRestore).toHaveBeenCalledWith(restoredSimulation);
  });

  it('restore 중 모든 불러오기 버튼을 비활성화해 중복 실행을 막는다', async () => {
    const secondSimulation = { ...simulation, id: 'sim-02', name: '두 번째 시뮬레이션' };
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ data: [simulation, secondSimulation], meta: { next_cursor: null, has_more: false } }))
      .mockImplementationOnce(() => new Promise(() => {}));

    render(<MyPage auth={auth} onBack={vi.fn()} onRestore={vi.fn()} />);
    const buttons = await screen.findAllByRole('button', { name: '불러오기' });
    await userEvent.click(buttons[0]);

    expect(screen.getByRole('button', { name: '불러오는 중...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '불러오기' })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('restore 실패 오류를 표시하고 다시 시도할 수 있다', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ data: [simulation], meta: { next_cursor: null, has_more: false } }))
      .mockImplementationOnce(() => response({}, 500));

    render(<MyPage auth={auth} onBack={vi.fn()} onRestore={vi.fn()} />);
    await userEvent.click(await screen.findByRole('button', { name: '불러오기' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.');
    expect(screen.getByRole('button', { name: '불러오기' })).toBeEnabled();
  });
});
