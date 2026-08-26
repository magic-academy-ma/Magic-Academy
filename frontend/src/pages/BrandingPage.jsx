import { useState } from 'react';
import { apiRequest } from '../api/client.js';
import './BrandingPage.css';

export default function BrandingPage({ auth, onEnroll }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleEnroll() {
    setLoading(true);
    setError('');
    try {
      const simulation = await apiRequest('/v1/simulations', {
        token: auth.access_token,
        method: 'POST',
        body: JSON.stringify({ name: 'Magic Academy Simulation' }),
      });
      onEnroll(simulation.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="branding-page">
      <div className="branding-page__content">
        <p className="branding-page__label">MAGIC ACADEMY</p>
        <h1 className="branding-page__title">
          마법이 살아 숨쉬는<br />마법 대학교
        </h1>
        <p className="branding-page__desc">
          마법사들이 관계를 맺고, 사건을 만들며, 세계를 변화시키는<br />
          멀티 에이전트 시뮬레이션에 오신 것을 환영합니다.
        </p>
        {error && (
          <p className="branding-page__error" role="alert">{error}</p>
        )}
        <button
          className="branding-page__btn"
          onClick={handleEnroll}
          disabled={loading}
        >
          {loading ? '입학 중...' : '입학하기'}
        </button>
      </div>
    </div>
  );
}
