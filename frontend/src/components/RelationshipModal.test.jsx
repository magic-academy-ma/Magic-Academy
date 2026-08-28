import { cleanup, render, screen, fireEvent, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import RelationshipModal from './RelationshipModal.jsx';
import * as client from '../api/client.js';

vi.mock('../api/client.js', () => ({
  apiRequest: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const selectedAgent = { id: 'agent-1', name: 'Adel', mbti_type: 'ISTJ' };
const agents = [
  { id: 'agent-1', name: 'Adel', mbti_type: 'ISTJ' },
  { id: 'agent-2', name: 'Leo', mbti_type: 'ESTP' },
  { id: 'agent-3', name: 'Ria', mbti_type: 'INFP' },
];
const auth = { access_token: 'tok' };

describe('RelationshipModal', () => {
  beforeEach(() => {
    client.apiRequest.mockResolvedValue([]);
  });

  it('dialog role과 제목을 렌더링한다', () => {
    render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={() => {}}
      />
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('관계 그래프')).toBeInTheDocument();
    expect(screen.getByText('Adel 선택 중')).toBeInTheDocument();
  });

  it('닫기 버튼 클릭 시 onClose가 호출된다', () => {
    const onClose = vi.fn();
    render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByLabelText('닫기'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('backdrop 클릭 시 onClose가 호출된다', () => {
    const onClose = vi.fn();
    render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByRole('dialog').parentElement);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('모든 Agent 노드 라벨을 렌더링한다', async () => {
    render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={() => {}}
      />
    );
    await screen.findByTestId('graph-node-agent-1'); // wait for loading to finish
    expect(screen.getByTestId('graph-node-agent-1')).toBeInTheDocument();
    expect(screen.getByTestId('graph-node-agent-2')).toBeInTheDocument();
    expect(screen.getByTestId('graph-node-agent-3')).toBeInTheDocument();
  });

  it('필터 chip을 클릭하면 해당 chip에 active 클래스가 추가된다', () => {
    render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={() => {}}
      />
    );
    const favorChip = screen.getByRole('button', { name: '호감·친밀' });
    expect(favorChip).not.toHaveClass('active');
    fireEvent.click(favorChip);
    expect(favorChip).toHaveClass('active');
  });

  it('scope chip을 클릭하면 해당 chip에 active 클래스가 추가된다', () => {
    render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={() => {}}
      />
    );
    const focusChip = screen.getByRole('button', { name: '선택 Agent 중심' });
    fireEvent.click(focusChip);
    expect(focusChip).toHaveClass('active');
  });

  it('다른 노드를 클릭하면 onSelectAgent가 해당 Agent와 함께 호출된다', async () => {
    const onSelectAgent = vi.fn();
    render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={onSelectAgent}
        onClose={() => {}}
      />
    );
    const leoNode = await screen.findByTestId('graph-node-agent-2');
    fireEvent.click(leoNode);
    expect(onSelectAgent).toHaveBeenCalledWith(agents[1]);
  });

  it('SVG 엣지 레이어가 렌더링된다', async () => {
    const { container } = render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={() => {}}
      />
    );
    await vi.waitFor(() => {
      expect(container.querySelector('svg.rm-svg')).toBeInTheDocument();
    });
  });

  it('범례 항목 5가지가 footer에 표시된다', () => {
    const { container } = render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={() => {}}
      />
    );
    const legend = container.querySelector('[aria-label="범례"]');
    expect(legend).toBeInTheDocument();
    expect(within(legend).getByText('호감·친밀')).toBeInTheDocument();
    expect(within(legend).getByText('신뢰')).toBeInTheDocument();
    expect(within(legend).getByText('긴장·라이벌')).toBeInTheDocument();
    expect(within(legend).getByText('의존')).toBeInTheDocument();
    expect(within(legend).getByText('중립')).toBeInTheDocument();
  });

  it('엣지 데이터가 있으면 API 응답을 바탕으로 SVG line을 렌더링한다', async () => {
    client.apiRequest.mockImplementation((path) => {
      if (path.includes('agent-1')) {
        return Promise.resolve([
          { target_agent_id: 'agent-2', affection: 80, closeness: 70, trust: 30, tension: 10, rivalry: 5, dependency: 20 },
        ]);
      }
      return Promise.resolve([]);
    });

    const { container } = render(
      <RelationshipModal
        selectedAgent={selectedAgent}
        agents={agents}
        auth={auth}
        onSelectAgent={() => {}}
        onClose={() => {}}
      />
    );

    await vi.waitFor(() => {
      const lines = container.querySelectorAll('svg.rm-svg line');
      expect(lines.length).toBeGreaterThan(0);
    });
  });
});
