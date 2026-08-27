import './SavePage.css';

export default function SavePage({ simulationName, onComplete, onCancel }) {
  function handleSave() {
    // TODO: 저장 API 확정 후 POST /v1/simulations/{simulationId}/save 호출로 교체한다.
    onComplete();
  }

  return (
    <main className="save-page">
      <section className="save-page__card">
        <p className="save-page__eyebrow">SAVE SIMULATION</p>
        <h1>시뮬레이션 저장</h1>
        <p><strong>{simulationName}</strong>의 현재 상태를 저장하시겠습니까?</p>
        <p className="save-page__notice">저장 API 연동은 준비 중입니다.</p>
        <div className="save-page__actions">
          <button type="button" onClick={handleSave}>저장</button>
          <button type="button" className="save-page__cancel" onClick={onCancel}>취소</button>
        </div>
      </section>
    </main>
  );
}
