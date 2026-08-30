import './SavePage.css';

export default function SavePage({ simulationName, onComplete, onCancel }) {
  return (
    <div className="save-bg-wrap">
      <div className="save-bg" aria-hidden="true" />
      <div className="save-overlay">
        <div className="save-modal" role="dialog" aria-modal="true" aria-labelledby="save-modal-title">
          <div className="save-modal__header">
            <h2 className="save-modal__title" id="save-modal-title">시뮬레이션 저장</h2>
            <button
              type="button"
              className="save-modal__close"
              onClick={onCancel}
              aria-label="닫기"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <path d="M3 3L11 11M11 3L3 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          <div className="save-modal__body">
            <div className="save-thumb">
              <div className="save-thumb__img" aria-hidden="true" />
              <div className="save-thumb__overlay" aria-hidden="true" />
              <div className="save-thumb__info">
                <div className="save-thumb__tick">TICK — · DAY —</div>
                <div className="save-thumb__name">{simulationName}</div>
              </div>
            </div>

            <div className="save-info-grid">
              <div className="save-info-item">
                <div className="save-info-item__key">Tick 수</div>
                <div className="save-info-item__val">—</div>
              </div>
              <div className="save-info-item">
                <div className="save-info-item__key">Agent 수</div>
                <div className="save-info-item__val">—</div>
              </div>
              <div className="save-info-item">
                <div className="save-info-item__key">경과 일수</div>
                <div className="save-info-item__val">—</div>
              </div>
              <div className="save-info-item">
                <div className="save-info-item__key">상태</div>
                <div className="save-info-item__val">—</div>
              </div>
            </div>

            <p className="message" role="status">
              Simulation과 Tick 결과는 실행할 때마다 자동으로 저장됩니다.
            </p>
            <p className="save-modal__hint">별도의 수동 저장 없이 안전하게 계속 진행할 수 있습니다.</p>
          </div>

          <div className="save-modal__footer">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onCancel}
            >
              돌아가기
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={onComplete}
            >
              확인
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
