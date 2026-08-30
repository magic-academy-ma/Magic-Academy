import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SavePage from './SavePage.jsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('SavePage', () => {
  it('자동 저장을 안내하고 확인하면 onComplete를 호출한다', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    const onComplete = vi.fn();

    render(
      <SavePage
        simulationName="첫 번째 시뮬레이션"
        onComplete={onComplete}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent('자동으로 저장됩니다');
    await userEvent.click(screen.getByRole('button', { name: '확인' }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it('닫기를 누르면 onCancel을 호출한다', async () => {
    const onCancel = vi.fn();
    render(
      <SavePage
        simulationName="첫 번째 시뮬레이션"
        onComplete={vi.fn()}
        onCancel={onCancel}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: '돌아가기' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
