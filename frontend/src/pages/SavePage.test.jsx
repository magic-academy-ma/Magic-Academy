import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SavePage from './SavePage.jsx';

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

describe('SavePage', () => {
  it('저장 API 성공 후 onComplete를 호출한다', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({ data: { id: 'sim-01' } }));
    const onComplete = vi.fn();

    render(
      <SavePage
        simulationName="첫 번째 시뮬레이션"
        simulationId="sim-01"
        token="token"
        onComplete={onComplete}
        onCancel={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/v1/simulations/sim-01/save',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it('저장 중 버튼을 비활성화해 중복 제출을 막는다', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}));

    render(
      <SavePage
        simulationName="첫 번째 시뮬레이션"
        simulationId="sim-01"
        token="token"
        onComplete={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const saveButton = screen.getByRole('button', { name: '저장' });
    await userEvent.click(saveButton);
    await userEvent.click(screen.getByRole('button', { name: '저장 중...' }));

    expect(screen.getByRole('button', { name: '저장 중...' })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('저장 실패 오류를 표시하고 다시 시도할 수 있다', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({}, 500));

    render(
      <SavePage
        simulationName="첫 번째 시뮬레이션"
        simulationId="sim-01"
        token="token"
        onComplete={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.');
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled();
  });
});
