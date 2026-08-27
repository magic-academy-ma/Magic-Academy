import { useState } from 'react';
import './PersonaSetupPage.css';

const CHAR_DATA = {
  adel: { name: 'Adel', mbti: 'ISTJ', major: '마법 도서관학과', interest: '규율',
          grade: 3, gender: '여', portrait: '/assets/character/Adel_ISTJ.png',
          desc: '원칙과 질서를 중시하는 수호계 마법학도. 마법 도서관의 규율을 철저히 지킵니다.' },
  leo:  { name: 'Leo',  mbti: 'ESTP', major: '마법공학과',      interest: '마법 생물',
          grade: 2, gender: '남', portrait: '/assets/character/Leo_ESTP.png',
          desc: '충동적이고 실용적인 Leo는 규칙보다 경험을 중시한다. 마법 생물과의 교감에 뛰어나며 위험한 상황도 즐긴다.' },
  ria:  { name: 'Ria',  mbti: 'INFP', major: '고대 마법',       interest: '룬 문자',
          grade: 1, gender: '여', portrait: '/assets/character/Ria_INFP.png',
          desc: '직관과 감수성이 풍부한 몽상가. 잊혀진 고대 룬 문자의 속삭임을 듣습니다.' },
  kai:  { name: 'Kai',  mbti: 'ENTJ', major: '마법 도구 제작',  interest: '아티팩트',
          grade: 4, gender: '남', portrait: '/assets/character/Kai_ENTJ.png',
          desc: '냉철한 전략가이자 아티팩트 제작자. 마법 사회의 효율적 구조를 설계하고자 합니다.' },
  sera: { name: 'Sera', mbti: 'ESFJ', major: '약초학 & 치유',   interest: '중재',
          grade: 2, gender: '여', portrait: '/assets/character/Sera_ESFJ.png',
          desc: '온화하고 친화력 있는 치유 마법사. 학생들 사이의 갈등을 중재하고 조화를 추구합니다.' },
};

const MBTI_DEFAULTS = {
  ISTJ: { openness: -20, conscientiousness: 35,  extraversion: -25, agreeableness: 10,  stability: 25  },
  ESTP: { openness: 15,  conscientiousness: -20, extraversion: 30,  agreeableness: -10, stability: 20  },
  INFP: { openness: 30,  conscientiousness: -10, extraversion: -20, agreeableness: 25,  stability: -15 },
  ENTJ: { openness: 20,  conscientiousness: 30,  extraversion: 25,  agreeableness: -15, stability: 20  },
  ESFJ: { openness: -5,  conscientiousness: 20,  extraversion: 20,  agreeableness: 35,  stability: 15  },
};

const BF_FIELDS = [
  { key: 'openness',        label: '개방성' },
  { key: 'conscientiousness', label: '성실성' },
  { key: 'extraversion',    label: '외향성' },
  { key: 'agreeableness',   label: '우호성' },
  { key: 'stability',       label: '정서 안정성' },
];

const MBTI_LIST = ['ISTJ', 'ESTP', 'INFP', 'ENTJ', 'ESFJ'];

function fmt(v) { return v >= 0 ? `+${v}` : `${v}`; }

export default function PersonaSetupPage({ charId = 'leo', onBack, onStart }) {
  const char = CHAR_DATA[charId] ?? CHAR_DATA.leo;

  const [selectedMbti, setSelectedMbti] = useState(char.mbti);
  const [bigFive, setBigFive] = useState(MBTI_DEFAULTS[char.mbti]);
  const [eventParams, setEventParams] = useState({ freq: 50, impact: 50 });
  const [magicParams, setMagicParams] = useState({ freq: 60, impact: 70, enabled: true });
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [importText, setImportText] = useState('');
  const [importError, setImportError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  function handleMbtiSelect(mbti) {
    setSelectedMbti(mbti);
    setBigFive(MBTI_DEFAULTS[mbti]);
  }

  function handleBigFiveChange(key, value) {
    setBigFive((prev) => ({ ...prev, [key]: Number(value) }));
  }

  function exportPreset() {
    const preset = {
      version: 1,
      mbti: selectedMbti,
      bigfive: bigFive,
      params: { event: eventParams, magic: magicParams },
    };
    const blob = new Blob([JSON.stringify(preset, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ma-preset-${charId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function applyImport() {
    try {
      const data = JSON.parse(importText);
      if (data.mbti && MBTI_DEFAULTS[data.mbti]) {
        setSelectedMbti(data.mbti);
      }
      if (data.bigfive) setBigFive({ ...MBTI_DEFAULTS[selectedMbti], ...data.bigfive });
      if (data.params?.event) setEventParams(data.params.event);
      if (data.params?.magic) setMagicParams(data.params.magic);
      setImportError('');
      setIsImportOpen(false);
      setImportText('');
    } catch {
      setImportError('올바른 JSON 형식이 아닙니다.');
    }
  }

  async function handleStart() {
    setIsLoading(true);
    setError('');
    try {
      await onStart(charId, {
        mbti: selectedMbti,
        bigFive,
        eventParams,
        magicParams,
      });
    } catch (err) {
      setError(err.message || '오류가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="persona-setup-page">
      {/* Portrait */}
      <div className="setup-portrait-panel">
        <div className="setup-portrait-panel__bg" style={{ backgroundImage: `url('${char.portrait}')` }} />
        <div className="setup-portrait-panel__overlay" />
        <div className="setup-portrait-panel__info">
          <div className="setup-portrait-panel__chips">
            <span className="chip chip-mbti">{selectedMbti}</span>
            <span className="chip chip-major">{char.major}</span>
          </div>
          <div className="setup-portrait-panel__name">{char.name}</div>
          <div className="setup-portrait-panel__sub">{selectedMbti} · {char.major} · {char.grade}학년</div>
          <div className="setup-portrait-panel__desc">{char.desc}</div>
        </div>
      </div>

      {/* Form */}
      <div className="setup-form-panel">
        <nav className="setup-nav">
          <button className="setup-nav__back" onClick={onBack} aria-label="이전">←</button>
          <span className="setup-nav__brand">Persona 초기 설정</span>
          <span className="setup-nav__char">— {char.name}</span>
          <div className="setup-nav__actions">
            <button className="btn-ghost-sm" onClick={() => setIsImportOpen(true)}>↑ JSON 가져오기</button>
            <button className="btn-ghost-sm" onClick={exportPreset}>↓ 내보내기</button>
          </div>
        </nav>

        <div className="setup-form-body">
          {/* 1. 기본 정보 */}
          <section>
            <div className="setup-section-title">기본 정보 (읽기 전용)</div>
            <div className="field-grid-2">
              {[
                { label: '학년', value: `${char.grade}학년` },
                { label: '전공', value: char.major },
                { label: '성별', value: char.gender },
                { label: '관심 분야', value: char.interest },
              ].map(({ label, value }) => (
                <div className="field-group" key={label}>
                  <label>{label}</label>
                  <div className="field-readonly">{value}</div>
                </div>
              ))}
            </div>
          </section>

          {/* 2. MBTI */}
          <section>
            <div className="setup-section-title">MBTI 선택</div>
            <div className="mbti-grid">
              {MBTI_LIST.map((mbti) => (
                <button
                  key={mbti}
                  className={`mbti-btn${selectedMbti === mbti ? ' selected' : ''}`}
                  onClick={() => handleMbtiSelect(mbti)}
                >
                  {mbti}
                </button>
              ))}
            </div>
            <div className="mbti-hint">MBTI 재선택 시 Big Five 전체 값이 초기화됩니다</div>
          </section>

          {/* 3. Big Five */}
          <section>
            <div className="setup-section-title">Big Five 성격 조정</div>
            <div className="bigfive-axis">
              <span />
              <span style={{ textAlign: 'left' }}>-50</span>
              <span>+50</span>
            </div>
            {BF_FIELDS.map(({ key, label }) => (
              <div className="bigfive-row" key={key}>
                <div className="bigfive-row__label">{label}</div>
                <input
                  type="range"
                  className="slider"
                  min={-50} max={50} step={5}
                  value={bigFive[key]}
                  onChange={(e) => handleBigFiveChange(key, e.target.value)}
                />
                <div className="bigfive-row__val">{fmt(bigFive[key])}</div>
              </div>
            ))}
          </section>

          {/* 4. 시뮬레이션 파라미터 */}
          <section>
            <div className="setup-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>시뮬레이션 파라미터 & Magic Layer 설정</span>
              <span className="chip chip-major" style={{ fontSize: 10 }}>
                MAGIC LAYER {magicParams.enabled ? 'ON' : 'OFF'}
              </span>
            </div>
            <div className="param-grid">
              <div className="param-card">
                <div className="param-card__header">
                  <span className="param-card__title">일반 Event</span>
                  <span className="param-card__tag">STANDARD</span>
                </div>
                {[
                  { label: '발생 빈도', key: 'freq' },
                  { label: '영향도', key: 'impact' },
                ].map(({ label, key }) => (
                  <div className="param-row" key={key}>
                    <span className="param-row__label">{label}</span>
                    <input
                      type="range" className="slider"
                      min={10} max={100} step={5}
                      value={eventParams[key]}
                      onChange={(e) => setEventParams((p) => ({ ...p, [key]: Number(e.target.value) }))}
                    />
                    <span className="param-row__val">{eventParams[key]}</span>
                  </div>
                ))}
              </div>

              <div className="param-card">
                <div className="param-card__header">
                  <span className="param-card__title magic">Magic Layer</span>
                  <div className="magic-toggle-row">
                    <label className="magic-toggle-label" htmlFor="magic-toggle">Magic OFF</label>
                    <input
                      id="magic-toggle"
                      type="checkbox"
                      checked={!magicParams.enabled}
                      onChange={(e) => setMagicParams((p) => ({ ...p, enabled: !e.target.checked }))}
                      style={{ accentColor: 'var(--c-primary)', cursor: 'pointer' }}
                    />
                  </div>
                </div>
                {[
                  { label: '발생 빈도', key: 'freq' },
                  { label: '영향도',   key: 'impact' },
                ].map(({ label, key }) => (
                  <div className="param-row" key={key}>
                    <span className="param-row__label">{label}</span>
                    <input
                      type="range" className="slider"
                      min={10} max={100} step={5}
                      value={magicParams[key]}
                      onChange={(e) => setMagicParams((p) => ({ ...p, [key]: Number(e.target.value) }))}
                    />
                    <span className="param-row__val magic">{magicParams[key]}</span>
                  </div>
                ))}
              </div>
            </div>

            {!magicParams.enabled && (
              <div className="magic-off-warning">
                ⚠️ <strong>Magic Layer OFF 적용 범위:</strong> 변환·특수 사건·World Effect가 비활성화되며 일반 사회 시뮬레이션만 진행됩니다.
              </div>
            )}
          </section>

          {error && <p className="setup-error" role="alert">{error}</p>}
        </div>

        <footer className="setup-footer">
          <span className="setup-footer__warning">
            시작 후 Persona와 Magic 설정은 잠깁니다. 일반 Event 설정은 실행 중 변경할 수 있으며 다음 Tick부터 적용됩니다.
          </span>
          <div className="setup-footer__actions">
            <button className="btn-outline-ma" onClick={onBack}>Persona 변경</button>
            <button className="btn-primary-ma" onClick={handleStart} disabled={isLoading}>
              {isLoading ? '시작 중...' : '시뮬레이션 시작 →'}
            </button>
          </div>
        </footer>
      </div>

      {/* JSON Import Modal */}
      {isImportOpen && (
        <div className="import-overlay" onClick={(e) => e.target === e.currentTarget && setIsImportOpen(false)}>
          <div className="import-modal">
            <div className="import-modal__header">
              <span className="import-modal__title">JSON 프리셋 가져오기</span>
              <button className="btn-ghost-sm" onClick={() => { setIsImportOpen(false); setImportError(''); }}>✕</button>
            </div>
            <p className="import-modal__desc">
              이전에 내보낸 <code>ma-preset-*.json</code> 파일 내용을 붙여넣으세요.<br />
              MBTI · Big Five · 시뮬레이션 파라미터가 일괄 적용됩니다.
            </p>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='{"version":1,"mbti":"ESTP","bigfive":{...},"params":{...}}'
            />
            {importError && <div className="import-error">{importError}</div>}
            <div className="import-modal__actions">
              <button className="btn-outline-ma" onClick={() => { setIsImportOpen(false); setImportError(''); }}>취소</button>
              <button className="btn-primary-ma" onClick={applyImport}>적용</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
