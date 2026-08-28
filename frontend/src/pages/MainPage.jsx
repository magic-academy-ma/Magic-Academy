import './MainPage.css';

const PLACEHOLDER_SIMS = [
  { id: 'placeholder-1', name: '첫 번째 시뮬레이션', meta: 'TICK 07 · LEO 시점', status: 'RUNNING' },
  { id: 'placeholder-2', name: 'Leo의 마법 생물 사건', meta: 'TICK 04 · RIA 시점', status: 'ENDED' },
];

const STATUS_CHIP = {
  RUNNING: { label: 'RUNNING', cls: 'sim-status--running' },
  PAUSED:  { label: 'PAUSED',  cls: 'sim-status--paused' },
  ENDED:   { label: 'ENDED',   cls: 'sim-status--ended' },
};

export default function MainPage({ displayName, onStart, onMyPage, simulations = [] }) {
  const cards = simulations.length > 0 ? simulations : PLACEHOLDER_SIMS;

  return (
    <div className="main-page">
      <section className="main-hero">
        <div className="main-hero__bg" />
        <div className="main-hero__overlay" />

        <nav className="main-nav" aria-label="주 내비게이션">
          <span className="main-nav__brand">
            <img src="/assets/concept/logo.png" alt="" width="34" height="34" />
            Magic Academy
          </span>
          <div className="main-nav__links">
            <span className="main-nav__link main-nav__link--active">홈</span>
            <button type="button" className="main-nav__link" onClick={onMyPage}>마이페이지</button>
          </div>
          <div className="main-nav__user">
            <button type="button" className="main-nav__profile-btn" onClick={onMyPage} aria-label="마이페이지로 이동">
              {displayName}
            </button>
          </div>
        </nav>

        <div className="main-hero__content">
          <p className="main-hero__eyebrow">MAGIC ACADEMY</p>
          <h1 className="main-hero__title">{displayName}님의 마법학교</h1>
          <p className="main-hero__sub">Agent들의 상태를 관찰하고, Magic Event의 원인을 추적합니다.</p>
          <div className="main-hero__cta">
            <button type="button" className="main-cta-primary" onClick={onStart}>
              시뮬레이션 시작
            </button>
            <button type="button" className="main-cta-outline" onClick={onMyPage}>
              기록 보기
            </button>
          </div>
        </div>
      </section>

      <main className="main-content">
        <div>
          <div className="section-header">
            <span className="section-title">이어서 관찰하기</span>
            <button type="button" className="section-more" onClick={onMyPage}>전체 보기 →</button>
          </div>
          <div className="sim-grid">
            {cards.map((sim) => {
              const chip = STATUS_CHIP[sim.status] ?? STATUS_CHIP.RUNNING;
              return (
                <div
                  key={sim.id}
                  className="sim-card"
                  role="button"
                  tabIndex={0}
                  onClick={onStart}
                  onKeyDown={(e) => e.key === 'Enter' && onStart()}
                >
                  <div className="sim-card__thumb">
                    <div className="sim-card__thumb-img" />
                    <div className="sim-card__thumb-overlay" />
                    <div className="sim-card__thumb-status">
                      <span className={`sim-status ${chip.cls}`}>{chip.label}</span>
                    </div>
                    <div className="sim-card__thumb-preview">
                      <span>▶ 이어서 관찰하기</span>
                    </div>
                  </div>
                  <div className="sim-card__body">
                    <div className="sim-card__name">{sim.name}</div>
                    <div className="sim-card__meta">{sim.meta}</div>
                  </div>
                </div>
              );
            })}

            <div
              className="sim-card sim-card--new"
              role="button"
              tabIndex={0}
              onClick={onStart}
              onKeyDown={(e) => e.key === 'Enter' && onStart()}
              aria-label="새 시뮬레이션 시작"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <span>새 시뮬레이션 시작</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
