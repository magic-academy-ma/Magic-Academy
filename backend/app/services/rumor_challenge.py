"""CHAPTER 1 저장/명령 서비스. 명령 행 잠금부터 Runtime·효과·영수증 저장까지 하나의 transaction으로 처리한다."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import Agent, Location, Relationship, RumorChallengeRun, Simulation
from app.services.fixtures import seed_slice_zero
from app.simulation.agent_runtime import Block
from app.simulation.challenge import rumor
from app.simulation.challenge.round_driver import run_forced_event_round
from app.simulation.challenge.rumor_runtime import RumorRuntime, executed_acts
from app.simulation.event_master import Event, ImpactLevel, IMPACT_LEVEL_TO_IMPORTANCE


def owned(db, run_id, owner, *, lock=False):
    query = select(RumorChallengeRun).where(RumorChallengeRun.id == run_id,
                                           RumorChallengeRun.owner_id == owner.id)
    if lock:
        query = query.with_for_update(nowait=True)
    try:
        run = db.scalar(query.execution_options(populate_existing=True))
    except OperationalError as exc:
        if lock and getattr(exc.orig, 'sqlstate', None) == '55P03':
            db.rollback()
            raise HTTPException(409, '현재 명령이 실행 중입니다. 완료 후 같은 요청으로 다시 확인하세요.') from exc
        raise
    if run is None:
        raise HTTPException(404, '챕터 기록을 찾을 수 없습니다.')
    return run


def response(db, run):
    agents = list(db.scalars(select(Agent).where(Agent.simulation_id == run.simulation_id).order_by(Agent.fixture_key)))
    s = run.private_state
    return dict(id=str(run.id), simulation_id=str(run.simulation_id), revision=run.revision,
                busy=run.pending is not None,
                intervention_opened_at=run.intervention_opened_at.isoformat() if run.intervention_opened_at else None,
                agents=[dict(id=str(a.id), name=a.name, agent_type=a.agent_type) for a in agents],
                observations=s.get('observations', []), investigations=s.get('investigations', []),
                incident=f"{next(a.name for a in agents if str(a.id) == s['roles']['subject'])} 학생이 금지된 마법을 사용했다는 소문이 퍼지고 있습니다.",
                **rumor.public_state(s))


def current(db, owner):
    run = db.scalar(select(RumorChallengeRun).where(RumorChallengeRun.owner_id == owner.id)
                    .order_by(RumorChallengeRun.created_at.desc()).limit(1))
    return response(db, run) if run else None


def start(db, owner, request_id, seed):
    existing = db.scalar(select(RumorChallengeRun).where(RumorChallengeRun.owner_id == owner.id,
                                                        RumorChallengeRun.start_request_id == request_id))
    if existing:
        if existing.seed != seed:
            raise HTTPException(409, '같은 요청 ID의 시작 설정이 다릅니다.')
        return response(db, existing)
    simulation = Simulation(id=uuid7(), owner_id=owner.id, name='CHAPTER 1 거짓 소문의 확산을 막아라', status='paused')
    db.add(simulation)
    try:
        db.flush()
        seed_slice_zero(db, simulation.id)
        db.flush()
        agents = list(db.scalars(select(Agent).where(Agent.simulation_id == simulation.id).order_by(Agent.fixture_key)))
        students = [str(a.id) for a in agents if a.agent_type == 'student']
        professor = next(str(a.id) for a in agents if a.agent_type == 'professor')
        state = rumor.initialize(students, professor, seed)
        # 기존 Policy의 첫 만남 기본값(0)을 모든 방향 관계의 초기 snapshot으로 명시한다.
        for source in agents:
            for target in agents:
                if source.id != target.id:
                    db.add(Relationship(id=uuid7(), simulation_id=simulation.id,
                        source_agent_id=source.id, target_agent_id=target.id))
        db.flush()
        state['initial_relationships'] = [dict(source=str(r.source_agent_id), target=str(r.target_agent_id),
            **{metric: getattr(r, metric) for metric in ('affection', 'closeness', 'trust', 'tension', 'rivalry', 'dependency')})
            for r in db.scalars(select(Relationship).where(Relationship.simulation_id == simulation.id))]
        state['observations'], state['investigations'], state['executions'] = [], [], []
        run = RumorChallengeRun(id=uuid7(), owner_id=owner.id, simulation_id=simulation.id,
            start_request_id=request_id, seed=seed, revision=0, private_state=state, receipts={})
        db.add(run)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(RumorChallengeRun).where(RumorChallengeRun.owner_id == owner.id,
                                                            RumorChallengeRun.start_request_id == request_id))
        if existing is None:
            raise
        if existing.seed != seed:
            raise HTTPException(409, '같은 요청 ID의 시작 설정이 다릅니다.')
        run = existing
    return response(db, run)


def _prepare(s, kind, payload):
    if s['tick'] >= rumor.TOTAL_TICKS:
        raise HTTPException(409, '이미 종료된 챕터입니다.')
    if kind == 'advance':
        if rumor.needs_intervention(s):
            raise HTTPException(409, '조사 후 개입을 먼저 선택하세요.')
        s['tick'] += 1
    elif kind == 'intervene':
        rumor.submit_intervention(s, payload['choice'], payload.get('target'), payload.get('information_id'), 0)
    elif kind == 'investigate':
        if not rumor.needs_intervention(s):
            raise HTTPException(409, '조사 가능한 단계가 아닙니다.')
        if payload['actor'] not in s['knowledge'] or payload['topic'] not in rumor.TOPICS:
            raise ValueError('대화 상대와 질문 주제를 확인하세요.')
        round_key = str((s['tick'] - 1) // rumor.TICKS_PER_ROUND + 1)
        count = s['inquiries'].get(round_key, 0)
        if count >= rumor.INQUIRIES_PER_ROUND:
            raise HTTPException(409, '이번 라운드의 조사 기회를 모두 사용했습니다.')
        if payload['topic'] == 'COMPARE':
            rumor.compare_statements(s, payload.get('statement_indices', []))
        s['inquiries'][round_key] = count + 1
    else:
        raise ValueError('알 수 없는 명령입니다.')


def _execute(db, run, state, kind, payload, runtime, request_id):
    if kind == 'intervene' or (kind == 'investigate' and payload['topic'] == 'COMPARE'):
        return
    actors = [payload['actor']] if kind == 'investigate' else state['students']
    # 관찰 장소를 제공할 뿐 TALK/증언/정정 행동은 지정하지 않는다.
    location = db.scalar(select(Location).where(Location.simulation_id == run.simulation_id,
                                                Location.code == 'central_square'))
    inquiry = dict(actor=payload['actor'], topic=payload['topic']) if kind == 'investigate' else None
    wrapper = RumorRuntime(runtime, state, inquiry=inquiry)
    event = Event(event_key=f'rumor:{request_id}', event_type='MEETING',
                  participant_agent_ids=tuple(actors), location_id=str(location.id), tick=state['tick'],
                  impact_level=ImpactLevel.LOW, importance=IMPACT_LEVEL_TO_IMPORTANCE[ImpactLevel.LOW],
                  title='학생 진술 조사' if inquiry else '학생자치위원회의 소문 조정 시간',
                  description='조정관이 대화를 요청했습니다.' if inquiry else '학생들이 이야기를 나눌 수 있는 시간입니다.',
                  source='challenge_controller')
    result = run_forced_event_round(db, simulation_id=run.simulation_id, run_id=request_id,
        tick_number=state['tick'], simulation_day=max(1, (state['tick'] - 1) // rumor.TICKS_PER_ROUND + 1),
        block=(Block.MORNING, Block.AFTERNOON, Block.EVENING)[(state['tick'] - 1) % rumor.TICKS_PER_ROUND],
        event=event, runtime=wrapper, non_mandatory_agent_ids=[UUID(a) for a in actors])
    raw = list(wrapper.raw_results.values())
    if raw and any(r['status'] == 'FALLBACK' for r in raw) and not any(r['status'] == 'PROPOSED' for r in raw):
        raise RuntimeError('chapter runtime unavailable')
    if inquiry:
        inquiry['event_id'] = wrapper.event_ids[payload['actor']]
    acts = executed_acts(result.runtime_results, wrapper.raw_results, inquiry=inquiry)
    if inquiry:
        answered = False
        for act in acts:
            if act['source_id'] == state['knowledge'][payload['actor']].get(act['information_id']):
                answered = rumor.investigate_answer(state, payload['actor'], payload['topic'], act['information_id']) or answered
        state['investigations'].append(dict(actor=payload['actor'], topic=payload['topic'], tick=state['tick'], answered=answered))
    else:
        rumor.apply_acts(state, acts)
    state['executions'].append(dict(request_id=str(request_id), results=wrapper.raw_results))
    state['observations'].extend(dict(actor=str(r.agent_id), tick=state['tick'], action=r.intent.action_type.value,
                                      status=r.status.value) for r in result.runtime_results)


def command(db: Session, owner, run_id, kind, payload, runtime=None):
    request_id = UUID(str(payload['request_id']))
    key = str(request_id)
    fingerprint = hashlib.sha256(json.dumps(dict(kind=kind, **payload), sort_keys=True, default=str).encode()).hexdigest()
    try:
        run = owned(db, run_id, owner, lock=True)
        receipt = run.receipts.get(key)
        if receipt:
            if receipt['fingerprint'] != fingerprint:
                raise HTTPException(409, '동일한 요청 ID로 다른 작업을 제출할 수 없습니다.')
            output = receipt['response']
            db.rollback()  # replay also releases the row lock immediately
            return output
        if run.pending is not None:
            raise HTTPException(409, '중단된 이전 실행 기록을 복구한 뒤 다시 시도하세요.')
        if payload['expected_revision'] != run.revision:
            raise HTTPException(409, '진행 상태가 변경되었습니다. 현재 기록을 다시 불러오세요.')
        state = deepcopy(run.private_state)
        try:
            _prepare(state, kind, payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if kind == 'intervene':
            now = datetime.now(timezone.utc)
            opened = run.intervention_opened_at
            if opened is None:
                raise HTTPException(409, '개입 시작 시각을 찾을 수 없습니다.')
            state['interventions'][-1]['elapsed_seconds'] = max(0, (now - opened).total_seconds())
        run.pending = dict(request_id=key, fingerprint=fingerprint)
        db.flush()  # never commit the reservation separately from its result
        _execute(db, run, state, kind, payload, runtime, request_id)
        simulation = db.get(Simulation, run.simulation_id)
        simulation.current_tick = state['tick']
        simulation.current_day = max(1, (state['tick'] - 1) // rumor.TICKS_PER_ROUND + 1)
        if state['tick'] == rumor.TOTAL_TICKS:
            rumor.finish(state)
            simulation.status = 'completed'
            simulation.ended_at = datetime.now(timezone.utc)
        if kind == 'advance' and rumor.needs_intervention(state):
            run.intervention_opened_at = datetime.now(timezone.utc)
        run.private_state, run.revision, run.pending = state, run.revision + 1, None
        db.flush()
        output = response(db, run)
        run.receipts = {**run.receipts, key: dict(fingerprint=fingerprint, response=output)}
        db.commit()
        return output
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        # COMMIT may have succeeded while its acknowledgement was lost. Read the
        # atomic receipt before permitting a retry, never apply its effects twice.
        try:
            stored = owned(db, run_id, owner)
            receipt = stored.receipts.get(key)
            if receipt and receipt['fingerprint'] == fingerprint:
                output = receipt['response']
                db.rollback()
                return output
        except Exception:
            pass  # DB may still be unavailable; a later GET/retry reads the receipt.
        db.rollback()
        raise HTTPException(503, '이번 명령을 완료하지 못했습니다. 진행 기록을 확인한 뒤 같은 요청으로 다시 시도하세요.') from exc


def recover(db: Session, owner, run_id, payload):
    """이전 구현/중단 실행의 예약만 해제한다. 틱·LLM·효과를 실행하지 않는다."""
    try:
        run = owned(db, run_id, owner, lock=True)
        if payload['expected_revision'] != run.revision:
            raise HTTPException(409, '진행 상태가 변경되었습니다. 현재 기록을 다시 불러오세요.')
        run.pending = None
        db.commit()
        return response(db, run)
    except Exception:
        db.rollback()
        raise
