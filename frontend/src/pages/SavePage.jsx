import { useState } from 'react';
import { apiRequest } from '../api/client.js';
import './SavePage.css';

export default function SavePage({ simulationName, simulationId, token, onComplete, onCancel }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSave() {
    setLoading(true);
    setError('');
    try {
      await apiRequest(`/v1/simulations/${simulationId}/save`, {
        method: 'POST',
        token,
      });
      onComplete();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="save-page">
      <section className="save-page__card">
        <p className="save-page__eyebrow">SAVE SIMULATION</p>
        <h1>시뮬레이션 저장</h1>
        <p><strong>{simulationName}</strong>의 현재 상태를 저장하시겠습니까?</p>
        {error && <p className="message error" role="alert">{error}</p>}
        <div className="save-page__actions">
          <button type="button" onClick={handleSave} disabled={loading}>
            {loading ? '저장 중...' : '저장'}
          </button>
          <button type="button" className="save-page__cancel" onClick={onCancel} disabled={loading}>취소</button>
        </div>
      </section>
    </main>
  );
}
