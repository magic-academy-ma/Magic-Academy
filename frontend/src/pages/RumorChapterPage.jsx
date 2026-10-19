import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../api/client.js';
import InspectorPanel from '../components/InspectorPanel.jsx';
import RelationshipModal from '../components/RelationshipModal.jsx';
import './RumorChapterPage.css';

const ROOT = '/v1/challenges/rumor';
const ACTIONS = { TALK: '대화', WAIT: '대기', REST: '휴식', AVOID: '회피', HELP: '도움', MOVE: '이동',
  STUDY: '공부', EAT: '식사', PARTICIPATE_EVENT: '대화 자리 참여', ATTEND_CLASS: '수업 참여', TEACH_CLASS: '수업 진행' };
const KINDS = { TRANSFER: '소문 전달', TESTIFY: '실제 증언', CORRECT: '실제 정정', PLAYER_SHARE: '조정관 정보 전달' };
const ENDINGS = { RESOLVED: '진실을 밝혀 소문을 완전히 해소했습니다.',
  MISUNDERSTANDING: '소문은 진정되었지만 일부 오해가 남았습니다.', SPREAD: '소문이 학교 전체로 확산되었습니다.' };

export default function RumorChapterPage({ auth, onBack, runId: storyRunId, onComplete }) {
  const [run, setRun] = useState(null);
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [relationships, setRelationships] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actor, setActor] = useState('');
  const [topic, setTopic] = useState('RUMOR');
  const [choice, setChoice] = useState('WATCH');
  const [information, setInformation] = useState('');
  const [comparison, setComparison] = useState([]);
  const pendingRequest = useRef(null);
  const startRequest = useRef(null);
  const token = auth.access_token;

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await apiRequest(storyRunId ? `${ROOT}/${storyRunId}` : `${ROOT}/current`, { token });
      setRun(result.data);
      pendingRequest.current = null;
      startRequest.current = null;
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [token, storyRunId]);
  useEffect(() => { load(); }, [load]); // 서버의 진행 기록으로 이어하기
  const runId = run?.id;
  const simulationId = run?.simulation_id;
  const revision = run?.revision;
  useEffect(() => {
    setActor(''); setTopic('RUMOR'); setChoice('WATCH'); setInformation('');
    setComparison([]); setSelected(null); setRelationships(false);
  }, [runId]);
  useEffect(() => {
    if (!simulationId) return;
    let active = true;
    apiRequest(`/v1/simulations/${simulationId}/agents`, { token })
      .then(list => { if (active) setAgents(list); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [simulationId, revision, token]);

  async function start() {
    setLoading(true); setError('');
    if (!startRequest.current) startRequest.current = { request_id: crypto.randomUUID(), seed: crypto.getRandomValues(new Uint32Array(1))[0] };
    try {
      const result = await apiRequest(ROOT, { token, method: 'POST', body: JSON.stringify(startRequest.current) });
      setRun(result.data); startRequest.current = null;
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }
  async function send(kind, values = {}) {
    setLoading(true); setError('');
    const request = pendingRequest.current ?? { kind, body: { request_id: crypto.randomUUID(), expected_revision: run.revision, ...values } };
    pendingRequest.current = request;
    try {
      const result = await apiRequest(`${ROOT}/${run.id}/${request.kind}`, { token, method: 'POST', body: JSON.stringify(request.body) });
      setRun(result.data); pendingRequest.current = null;
      setComparison([]);
    } catch (e) {
      setError(e.message);
      if (e.status && e.status < 500) pendingRequest.current = null;
    } finally { setLoading(false); }
  }
  async function recover() {
    setLoading(true); setError('');
    try {
      const result = await apiRequest(`${ROOT}/${run.id}/recover`, { token, method: 'POST',
        body: JSON.stringify({ request_id: crypto.randomUUID(), expected_revision: run.revision }) });
      setRun(result.data); pendingRequest.current = null;
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }
  const name = id => id === 'player' ? '조정관' : run?.agents.find(a => a.id === id)?.name ?? '학생';
  const selectedAgent = agents.find(a => a.id === selected);
  const completed = run?.status === 'completed';
  const disabled = loading || run?.busy;
  const target = actor || run?.agents.find(a => a.agent_type === 'student')?.id || '';
  const info = information || run?.information[0]?.id || '';

  return <main className="rumor-page">
    <header className="rumor-header"><button onClick={onBack}>메인으로</button><span>스토리모드 · CHAPTER 1</span>
      <button onClick={load} disabled={loading}>진행 기록 새로 불러오기</button></header>
    <section className="panel rumor-intro">
      <h1>거짓 소문의 확산을 막아라</h1>
      <p>당신은 학생자치위원회의 임시 조정관입니다. 학기 초, 한 학생이 수업 중 금지된 마법을 몰래 사용했다는 소문이 퍼집니다.</p>
      <p>학생들의 진술을 비교하고 출처를 추적하세요. 당사자나 교수에게 사실을 확인하고, 소문이 학교 전체로 퍼지기 전에 대응하는 것이 목표입니다.</p>
      {run && <p>{run.incident}</p>}
      <p>부탁을 받은 학생이 증언하거나 정정할지는 스스로 결정합니다.</p>
      {!run && !storyRunId && <button className="main-cta-primary" disabled={loading} onClick={start}>CHAPTER 1 시작</button>}
    </section>
    {error && <p role="alert">{error}</p>}
    {loading && <p role="status">진행 기록을 확인하고 있습니다…</p>}
    {pendingRequest.current && !loading && <button onClick={() => send(pendingRequest.current.kind)}>같은 요청 결과 다시 확인</button>}
    {run && <>
      <section className="panel rumor-progress">
        <h2>{run.current_round}라운드 · {run.current_tick} / 9틱</h2>
        <p>{run.school_spread ? '학교 전체로 소문이 확산된 기록이 있습니다.' : '학생들의 반응을 살피며 정보를 확인하세요.'}</p>
        {Number.isFinite(run.rumor_awareness_count) && <p>소문을 접한 학생 {run.rumor_awareness_count}명 · 현재 오해가 남은 학생 {run.misinformed_count}명</p>}
        {run.busy && <><p role="status">이전 실행 기록이 남아 있습니다. 복구하면 진행을 바꾸지 않고 잠금만 해제합니다. 실행 중인 명령은 중단하지 않습니다.</p>
          <button disabled={loading} onClick={recover}>중단된 실행 복구</button></>}
        {!completed && !run.needs_intervention && <button disabled={disabled} onClick={() => send('advance')}>다음 틱 관찰</button>}
      </section>
      <div className="rumor-columns">
        <section className="panel"><h2>학생 행동 관찰</h2>
          <div className="rumor-agent-list">{run.agents.map(a => <button key={a.id} onClick={() => setSelected(a.id)}>{a.name} 상태·관계</button>)}</div>
          {run.observations.length === 0 && <p>다음 틱을 진행하면 학생들의 행동을 볼 수 있습니다.</p>}
          <ol className="rumor-observations" aria-label="틱별 행동 기록">{run.observations.map((o, i) => <li key={i}>{o.tick}틱 · {name(o.actor)} — {ACTIONS[o.action] ?? '활동'}{o.status === 'FALLBACK' ? ' (대화 불성립 또는 판단 보류)' : ''}</li>)}</ol>
          <h3>실제로 오간 이야기</h3>
          {run.history.length === 0 && <p>아직 관찰한 전달·증언·정정이 없습니다.</p>}
          <ol>{run.history.map((e, i) => <li key={i}>{e.tick}틱 · {name(e.actor)} → {name(e.target)} · {KINDS[e.kind]}<p>“{e.text}”</p></li>)}</ol>
        </section>
        {selectedAgent && <section className="panel"><InspectorPanel agent={selectedAgent} simulationId={run.simulation_id} token={token} currentTick={run.current_tick} onClose={() => setSelected(null)} />
          <button onClick={() => setRelationships(true)}>관계 보기</button></section>}
      </div>
      {!completed && run.needs_intervention && <section className="panel rumor-controls">
        <h2>조사와 개입</h2><p>조사는 이번 라운드에 {run.inquiries_remaining}회 남았습니다. 개입을 제출하면 다음 틱으로 진행할 수 있습니다.</p>
        <label>대화 상대<select aria-label="대화 상대" value={target} onChange={e => setActor(e.target.value)}>{run.agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        <label>질문 주제<select value={topic} onChange={e => setTopic(e.target.value)}>{run.topics.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}</select></label>
        <button disabled={disabled || !run.inquiries_remaining || (topic === 'COMPARE' && comparison.length !== 2)} onClick={() => send('investigate', { actor: target, topic, statement_indices: comparison })}>조사·대화하기</button>
        <label>개입 방식<select value={choice} onChange={e => setChoice(e.target.value)}>{run.choices.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
        <label>전달하거나 요청할 정보<select value={info} onChange={e => setInformation(e.target.value)}><option value="">정보를 선택하세요</option>{run.information.map(i => <option key={i.id} value={i.id}>{i.text}</option>)}</select></label>
        <p>출처 진술은 비교 기록으로 사용하세요. 사실을 전달하려면 당사자 또는 교수에게 확인해야 합니다.</p>
        <p>증언·정정·정보 전달의 대상은 위에서 고른 학생입니다. 교수에게는 조사 질문을 할 수 있습니다.</p>
        <button disabled={disabled || (['SHARE', 'REQUEST_TESTIMONY', 'REQUEST_CORRECTION'].includes(choice) && (!info || run.agents.find(a => a.id === target)?.agent_type !== 'student')) || (choice === 'SHARE' && (info === 'S' || (info === 'F' && !run.information.some(i => i.id === 'F' && i.confirmed)))) || (choice === 'PUBLISH_FACT' && !run.information.some(i => i.id === 'F' && i.confirmed))}
          onClick={() => send('intervene', { choice, target, information_id: info || null })}>개입 제출</button>
      </section>}
      <section className="panel"><h2>들은 진술과 사실 확인 기록</h2>
        <p>서로 다른 학생의 진술 두 개를 선택하고 ‘진술 비교’를 질문 주제로 제출하세요.</p>
        {run.statements.map((s, i) => <label className="rumor-statement" key={i}><input type="checkbox" checked={comparison.includes(i)} disabled={completed || disabled}
          onChange={e => setComparison(old => e.target.checked ? [...old, i].slice(-2) : old.filter(v => v !== i))} />
          {name(s.actor)} · {s.tick}틱 · “{s.text}”</label>)}
        <ul>{run.information.map(i => <li key={i.id}>{i.confirmed ? '확인된 사실' : '들은 진술 · 미확인'} — {i.text}</li>)}</ul>
        {run.investigations.filter(i => !i.answered).map((i, n) => <p key={n}>{name(i.actor)}에게 질문했지만 확인할 진술을 얻지 못했습니다.</p>)}
        <h3>제출한 개입</h3><ul>{run.interventions.map((i, n) => <li key={n}>{i.tick}틱 · {run.choices.find(c => c.value === i.choice)?.label} · {i.target && i.target !== 'all' ? name(i.target) : '전체 상황'} — 실제 반응은 관찰 기록에서 확인하세요.</li>)}</ul>
      </section>
      {completed && <section className="panel rumor-ending"><h2>챕터 종료</h2><p>{ENDINGS[run.ending]}</p><h3>달성 업적</h3>
        <ul>{run.achievements.map(a => <li key={a.id}>{a.label}</li>)}</ul>
        {onComplete ? <button disabled={loading} onClick={onComplete}>활동 기록 남기고 계속</button> : <button disabled={loading} onClick={start}>새 챕터 시작</button>}</section>}
      {run.busy && !storyRunId && <button disabled={loading} onClick={start}>새 챕터 시작</button>}
    </>}
    {relationships && selectedAgent && <RelationshipModal selectedAgent={selectedAgent} agents={agents} auth={auth} onSelectAgent={a => setSelected(a.id)} onClose={() => setRelationships(false)} />}
  </main>;
}
