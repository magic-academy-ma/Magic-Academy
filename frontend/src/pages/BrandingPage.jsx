import { useState } from 'react';
import { apiRequest } from '../api/client.js';
import './BrandingPage.css';

const SLIDES = [
  {
    badge: 'Multi-Agent Simulation',
    badgeColor: '#d4b26f',
    badgeBg: 'rgba(212, 178, 111, 0.14)',
    badgeBorder: 'rgba(212, 178, 111, 0.35)',
    charName: 'Leo',
    mbti: 'ESTP',
    charImg: '/assets/character/Leo_ESTP.png',
    nameColor: '#d4b26f',
    ringColor: '#d4b26f',
    bubbleBorder: 'rgba(70, 100, 180, 0.24)',
    text: '안녕! 여긴 마법학교야.\n우리는 너의 지시 없이도, 알아서 관계 맺고 갈등하고 사건을 만들어.',
  },
  {
    badge: 'Agent Intelligence',
    badgeColor: '#5e60e8',
    badgeBg: 'rgba(94, 96, 232, 0.14)',
    badgeBorder: 'rgba(94, 96, 232, 0.38)',
    charName: 'Adel',
    mbti: 'ISTJ',
    charImg: '/assets/character/Adel_ISTJ.png',
    nameColor: '#db4c4c',
    ringColor: '#db4c4c',
    bubbleBorder: 'rgba(219, 76, 76, 0.38)',
    text: '결계의 순환이 불규칙해...\n규율은 지켜야 하는데, 피로가 너무 누적됐어.',
  },
  {
    badge: 'Causal Observatory',
    badgeColor: '#34b3c7',
    badgeBg: 'rgba(52, 179, 199, 0.14)',
    badgeBorder: 'rgba(52, 179, 199, 0.32)',
    charName: 'Inspector',
    mbti: null,
    charImg: null,
    nameColor: '#34b3c7',
    ringColor: '#34b3c7',
    bubbleBorder: 'rgba(52, 179, 199, 0.32)',
    text: 'Magic Event가 발생하면,\n1문장 서사와 정밀 인과를 함께 보여드릴게요.',
  },
];

export default function BrandingPage({ auth, onEnroll }) {
  const [slide, setSlide] = useState(1);
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
      onEnroll(simulation);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleCta() {
    if (slide < SLIDES.length) {
      setSlide(slide + 1);
    } else {
      handleEnroll();
    }
  }

  const current = SLIDES[slide - 1];
  const isLast = slide === SLIDES.length;

  return (
    <div className="branding-page">
      <button className="ob-skip" onClick={handleEnroll} disabled={loading}>
        건너뛰기 →
      </button>

      <div className="ob-slide-wrap">
        <div className="onboarding__brand">MAGIC ACADEMY</div>

        <div className="ob-slide-content" key={slide}>
          <div
            className="ob-badge"
            style={{ background: current.badgeBg, borderColor: current.badgeBorder }}
          >
            <div
              className="ob-badge-dot"
              style={{ background: current.badgeColor, boxShadow: `0 0 6px ${current.badgeColor}` }}
            />
            <span className="ob-badge-text" style={{ color: current.badgeColor }}>
              {current.badge}
            </span>
          </div>

          <div className="chat-msg">
            {current.charImg ? (
              <div
                className="chat-avatar"
                style={{
                  backgroundImage: `url(${current.charImg})`,
                  borderColor: current.ringColor,
                  boxShadow: `0 0 16px ${current.ringColor}66`,
                }}
                role="img"
                aria-label={`${current.charName} 아바타`}
              />
            ) : (
              <div
                className="chat-avatar chat-avatar--glyph"
                style={{ borderColor: current.ringColor, boxShadow: `0 0 16px ${current.ringColor}66` }}
                aria-label="Inspector 아바타"
              >
                ◎
              </div>
            )}
            <div className="chat-bubble" style={{ borderColor: current.bubbleBorder }}>
              <div className="chat-name" style={{ color: current.nameColor }}>
                {current.charName}{current.mbti ? ` · ${current.mbti}` : ''}
              </div>
              <div className="chat-text">
                {current.text.split('\n').map((line, i, arr) => (
                  <span key={i}>{line}{i < arr.length - 1 && <br />}</span>
                ))}
              </div>
            </div>
          </div>

          {error && <p className="ob-error" role="alert">{error}</p>}
        </div>

        <button className="ob-cta" onClick={handleCta} disabled={loading}>
          {loading ? '시작 중...' : isLast ? '시작하기' : '다음 →'}
        </button>

        <div className="ob-pagination">
          <div className="ob-dots">
            {SLIDES.map((_, i) => (
              <div
                key={i}
                className={`ob-dot${slide === i + 1 ? ' active' : ''}`}
                onClick={() => setSlide(i + 1)}
                role="button"
                aria-label={`${i + 1}번째 슬라이드로 이동`}
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && setSlide(i + 1)}
              />
            ))}
          </div>
          <span className="ob-pagenum">
            {String(slide).padStart(2, '0')} / {String(SLIDES.length).padStart(2, '0')}
          </span>
        </div>
      </div>
    </div>
  );
}
