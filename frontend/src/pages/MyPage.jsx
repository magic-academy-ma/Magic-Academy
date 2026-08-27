import { useEffect, useState } from 'react';
import { apiRequest } from '../api/client.js';
import './MyPage.css';

function formatSavedAt(simulation) {
  const value = simulation.saved_at ?? simulation.updated_at ?? simulation.created_at;
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ko-KR');
}

export default function MyPage({ auth, onBack }) {
  const [simulations, setSimulations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiRequest('/v1/simulations', { token: auth.access_token })
      .then((result) => { if (active) setSimulations(result); })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [auth.access_token]);

  return (
    <main className="my-page">
      <section className="my-page__content">
        <div className="my-page__header">
          <div><p>MY PAGE</p><h1>내 시뮬레이션</h1></div>
          <button type="button" onClick={onBack}>뒤로가기</button>
        </div>
        {loading && <p className="my-page__message">목록을 불러오는 중...</p>}
        {error && <p className="my-page__message my-page__error" role="alert">{error}</p>}
        {!loading && !error && simulations.length === 0 && <p className="my-page__message">저장된 시뮬레이션이 없습니다.</p>}
        {!loading && !error && simulations.length > 0 && (
          <ul className="my-page__list">
            {simulations.map((item) => (
              <li key={item.id}>
                <div><strong>{item.name}</strong><span>{formatSavedAt(item)} · {item.status}</span></div>
                <button type="button" disabled title="준비 중">불러오기 · 준비 중</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
