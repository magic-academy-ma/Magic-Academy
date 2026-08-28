import { useEffect, useState } from 'react';
import { apiRequest } from '../api/client.js';
import './MyPage.css';

function formatSavedAt(simulation) {
  const value = simulation.saved_at ?? simulation.updated_at ?? simulation.created_at;
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ko-KR');
}

function statusLabel(status) {
  const map = { observing: '관찰 중', saved: '저장됨', complete: '완료' };
  return map[status] ?? status;
}

function statusClass(status) {
  return ['observing', 'saved', 'complete'].includes(status) ? status : '';
}

export default function MyPage({ auth, onBack, onRestore }) {
  const [simulations, setSimulations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [restoringId, setRestoringId] = useState(null);
  const [restoreError, setRestoreError] = useState('');

  useEffect(() => {
    let active = true;
    apiRequest('/v1/simulations', { token: auth.access_token })
      .then((result) => {
        if (active) setSimulations(result.data);
      })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [auth.access_token]);

  async function handleRestore(id) {
    setRestoringId(id);
    setRestoreError('');
    try {
      const result = await apiRequest(`/v1/simulations/${id}/restore`, {
        method: 'POST',
        token: auth.access_token,
        body: JSON.stringify({}),
      });
      onRestore(result.data);
    } catch (requestError) {
      setRestoreError(requestError.message);
    } finally {
      setRestoringId(null);
    }
  }

  const avatarChar = (auth.user?.display_name?.[0] ?? 'O').toUpperCase();

  return (
    <div className="mypage-shell">
      <header className="mypage-topbar">
        <button type="button" className="btn btn-ghost btn-sm" onClick={onBack}>뒤로가기</button>
        <span className="mypage-brand">Magic Academy · 마이페이지</span>
      </header>

      <div className="mypage-layout">
        <aside className="mypage-sidebar">
          <div className="observer">
            <div className="observer__avatar">{avatarChar}</div>
            <div>
              <div className="observer__name">{auth.user?.display_name}</div>
              <div className="observer__email">{auth.user?.username}</div>
            </div>
          </div>
          <nav className="mypage-menu" aria-label="마이페이지 메뉴">
            <button type="button" className="mypage-menu__item active" aria-current="page">시뮬레이션</button>
            <button type="button" className="mypage-menu__item" disabled aria-disabled="true">Persona</button>
            <button type="button" className="mypage-menu__item" disabled aria-disabled="true">관찰 통계</button>
            <button type="button" className="mypage-menu__item" disabled aria-disabled="true">프로필 및 계정</button>
          </nav>
        </aside>

        <main className="mypage-content">
          <header className="page-header">
            <div>
              <div className="page-eyebrow">Saved Worlds</div>
              <h1 className="page-title">내 시뮬레이션</h1>
              <p className="page-description">저장한 시뮬레이션을 확인하고 이어서 관찰할 수 있습니다.</p>
            </div>
          </header>

          {restoreError && (
            <p className="mypage-message mypage-message--error" role="alert">{restoreError}</p>
          )}
          {loading && (
            <p className="mypage-message">목록을 불러오는 중...</p>
          )}
          {error && (
            <p className="mypage-message mypage-message--error" role="alert">{error}</p>
          )}
          {!loading && !error && simulations.length === 0 && (
            <p className="mypage-message">저장된 시뮬레이션이 없습니다.</p>
          )}
          {!loading && !error && simulations.length > 0 && (
            <div className="sim-grid">
              {simulations.map((item) => (
                <article key={item.id} className="sim-card">
                  <div className="sim-card__thumb" aria-hidden="true" />
                  <div className="sim-card__body">
                    <h2 className="sim-card__name">{item.name}</h2>
                    <div className="sim-card__meta">
                      <span className="sim-card__date">{formatSavedAt(item)}</span>
                      {item.status && (
                        <span className={`sim-card__status-chip ${statusClass(item.status)}`}>
                          {statusLabel(item.status)}
                        </span>
                      )}
                    </div>
                    <div className="sim-card__actions">
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        disabled={restoringId !== null}
                        onClick={() => handleRestore(item.id)}
                      >
                        {restoringId === item.id ? '불러오는 중...' : '불러오기'}
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
