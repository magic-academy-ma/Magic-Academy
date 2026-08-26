import { useState } from 'react';
import './PersonaSelectPage.css';

const PERSONAS = [
  {
    id: 'adel',
    name: 'Adel',
    mbti: 'ISTJ',
    major: '방어 마법',
    traits: ['성실', '내향', '원칙주의'],
    portrait: '/assets/character/Adel_ISTJ.png',
  },
  {
    id: 'leo',
    name: 'Leo',
    mbti: 'ESTP',
    major: '마법 생물',
    traits: ['충동적', '외향', '실용주의'],
    portrait: '/assets/character/Leo_ESTP.png',
  },
  {
    id: 'ria',
    name: 'Ria',
    mbti: 'INFP',
    major: '고대 마법',
    traits: ['몽상적', '내향', '감수성'],
    portrait: '/assets/character/Ria_INFP.png',
  },
  {
    id: 'kai',
    name: 'Kai',
    mbti: 'ENTJ',
    major: '마법 도구 제작',
    traits: ['리더십', '외향', '전략적'],
    portrait: '/assets/character/Kai_ENTJ.png',
  },
  {
    id: 'sera',
    name: 'Sera',
    mbti: 'ESFJ',
    major: '약초학 & 치유',
    traits: ['사교적', '친화력', '조화'],
    portrait: '/assets/character/Sera_ESFJ.png',
  },
];

function PersonaCard({ persona, selected, onSelect }) {
  return (
    <div
      className={`persona-card${selected ? ' selected' : ''}`}
      onClick={onSelect}
      role="button"
      aria-pressed={selected}
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
    >
      <span className="selected-badge" aria-hidden="true">선택됨</span>
      <div
        className="persona-card__portrait"
        style={{ backgroundImage: `url('${persona.portrait}')` }}
      />
      <div className="persona-card__info">
        <div className="persona-card__name">{persona.name}</div>
        <div className="persona-card__mbti">{persona.mbti}</div>
        <div className="persona-card__major">{persona.major}</div>
        <div className="persona-traits">
          {persona.traits.map((trait) => (
            <span key={trait} className="trait-tag">{trait}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function PersonaSelectPage({ onConfirm, fromMain = false }) {
  const [selectedId, setSelectedId] = useState('leo');
  const selected = PERSONAS.find((p) => p.id === selectedId);

  return (
    <div className="persona-select-page">
      <div className="page-body">
        <a
          href={fromMain ? '/main' : '/onboarding'}
          className="back-link"
          aria-label="이전 화면으로 돌아가기"
        >
          ← 이전
        </a>

        <div className="page-title">
          <div className="page-step">PERSONA 선택 · 2 / 3</div>
          <h1 className="page-title__main">관찰할 Persona를 선택하세요</h1>
          <p className="page-title__sub">
            선택한 Persona의 시점으로 세계를 관찰합니다. 나중에 변경할 수 없습니다.
          </p>
        </div>

        <div className="card-row">
          {PERSONAS.map((persona) => (
            <PersonaCard
              key={persona.id}
              persona={persona}
              selected={selectedId === persona.id}
              onSelect={() => setSelectedId(persona.id)}
            />
          ))}
        </div>
      </div>

      <footer className="page-footer">
        <div className={`selected-summary${selected ? ' visible' : ''}`}>
          {selected && (
            <>
              <div
                className="selected-summary__portrait"
                style={{ backgroundImage: `url('${selected.portrait}')` }}
                aria-hidden="true"
              />
              <div>
                <div className="selected-summary__name">{selected.name}</div>
                <div className="selected-summary__mbti">
                  {selected.mbti} · {selected.major}
                </div>
              </div>
            </>
          )}
        </div>

        <button
          className="btn-primary-ma"
          onClick={() => onConfirm(selectedId)}
          disabled={!selectedId}
        >
          이 Persona로 시작하기 →
        </button>
      </footer>
    </div>
  );
}
