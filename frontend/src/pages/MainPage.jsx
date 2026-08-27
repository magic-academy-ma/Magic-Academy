import './MainPage.css';

export default function MainPage({ displayName, onStart, onMyPage }) {
  return (
    <main className="main-page">
      <section className="main-page__card">
        <p className="main-page__eyebrow">MAGIC ACADEMY</p>
        <h1>{displayName}님, 환영합니다.</h1>
        <p className="main-page__description">마법 대학교의 새로운 이야기를 시작해 보세요.</p>
        <div className="main-page__actions">
          <button type="button" className="main-page__primary" onClick={onStart}>시뮬레이션 시작</button>
          <button type="button" className="main-page__secondary" onClick={onMyPage}>마이페이지</button>
        </div>
      </section>
    </main>
  );
}
