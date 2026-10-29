import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import Relationship, RumorChallengeRun, RuntimeResult, User
from app.main import app
from app.services import rumor_challenge as service
from app.services.runtime_dependency import get_agent_runtime
from app.simulation.agent_runtime import AgentRuntime, MockLLMClient


class ChapterClient:
    """Production Runtime schema・충돌 해소・Policy를 그대로 사용하는 테스트 LLM."""
    def __init__(self, plans=None):
        self.calls = []
        self.plans = plans or {}

    def generate(self, inp):
        self.calls.append(inp)
        result = MockLLMClient().generate(inp)
        actor, context = str(inp.agent.agent_id), inp.rumor_context
        if context.get('inquiry'):
            topic = context['inquiry']['topic']
            wanted = {'VERIFY': ['F'], 'SOURCE': ['S', 'R0', 'R1', 'R2'],
                      'OBSERVED': ['F', 'S'], 'RUMOR': ['R2', 'R1', 'R0']}[topic]
            info = next((i for i in wanted if i in context['information']), None)
            if info:
                result.update(action_type='PARTICIPATE_EVENT', target_location_id=None,
                              related_event_id=str(inp.schedule.event_id),
                              rumor_acts=[dict(kind='ANSWER', information_id=info, target='player',
                                               source_id=context['information'][info]['source_id'])])
        elif actor in self.plans:
            target, kind, info = self.plans[actor]
            source = context['information'].get(info, context['possible_distortions'].get(info))
            result.update(action_type='TALK', target_agent_id=target, target_location_id=None,
                          rumor_acts=[] if kind is None else [dict(kind=kind, information_id=info, target=target,
                                           source_id=source['source_id'] if source else actor)])
            result['reaction']['relationship_signals'] = [dict(signal_type='TRUST_UP', intensity='LOW', target_agent_id=target)]
        result['utterance'] = '비공개 설명 sentinel'
        result['motivation_summary'] = '비공개 동기 sentinel'
        result['decision_explanation']['alternatives'][0]['action_type'] = result['action_type']
        return result


@pytest.fixture
def engine():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL required')
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def setup(engine):
    with Session(engine, expire_on_commit=False) as db:
        owner = User(id=uuid4(), username=str(uuid4()), display_name='조정관', password_hash='test', roles=['USER'])
        db.add(owner)
        db.commit()
        output = service.start(db, owner, uuid4(), 7)
        run = db.get(RumorChallengeRun, UUID(output['id']))
        yield db, owner, run


def payload(run, **kwargs):
    return dict(request_id=str(uuid4()), expected_revision=run.revision, **kwargs)


def runtime(client=None):
    return AgentRuntime(client or ChapterClient(), model='rumor-test')


def call(db, owner, run, kind, client=None, **kwargs):
    return service.command(db, owner, run.id, kind, payload(run, **kwargs), runtime(client))


def test_start_resume_owner_privacy_and_idempotency(setup):
    db, owner, run = setup
    out = service.start(db, owner, run.start_request_id, run.seed)
    assert out['id'] == str(run.id)
    assert 'roles' not in str(out) and 'seed' not in out and not out['information']
    with pytest.raises(HTTPException) as error:
        service.owned(db, run.id, User(id=uuid4()))
    assert error.value.status_code == 404
    assert service.current(db, owner)['id'] == str(run.id)
    request, client = payload(run), ChapterClient()
    result = service.command(db, owner, run.id, 'advance', request, runtime(client))
    assert result['current_tick'] == 1 and len(client.calls) == 5
    assert service.command(db, owner, run.id, 'advance', request, runtime(client)) == result
    assert len(client.calls) == 5
    with pytest.raises(HTTPException) as error:
        call(db, owner, run, 'advance', client)
    assert error.value.status_code == 409
    db.rollback()
    for row in db.scalars(select(RuntimeResult).where(RuntimeResult.agent_id.in_([UUID(a) for a in run.private_state['students']]))):
        assert 'sentinel' not in str(row.intent) and row.intent['rumor_acts'] == []


def test_runtime_transmission_and_policy(setup):
    db, owner, run = setup
    a, b = [run.private_state['roles'][r] for r in ('origin', 'subject')]
    plans = {a: (b, 'TRANSFER', 'R1'), b: (a, 'TESTIFY', 'F')}
    relation = db.scalar(select(Relationship).where(Relationship.source_agent_id == UUID(a), Relationship.target_agent_id == UUID(b)))
    trust_before = relation.trust
    result = call(db, owner, run, 'advance', ChapterClient(plans))
    assert any(h['kind'] == 'TRANSFER' and h['target'] == b and h['information_id'] == 'R1' for h in result['history'])
    db.refresh(relation)
    assert relation.trust > trust_before
    assert run.private_state['knowledge'][a]['F'] == b
    assert 'sentinel' not in str(result)
    assert len(run.private_state['executions'][-1]['results']) == 5


def test_unmatched_talk_cannot_transfer(setup):
    db, owner, run = setup
    a, b = [run.private_state['roles'][r] for r in ('origin', 'subject')]
    result = call(db, owner, run, 'advance', ChapterClient({a: (b, 'TRANSFER', 'R0')}))
    assert not result['history']
    assert any(o['actor'] == a and o['status'] == 'FALLBACK' for o in result['observations'])


def test_investigation_save_limits_and_completion(setup):
    db, owner, run = setup
    client = ChapterClient()
    call(db, owner, run, 'advance', client)
    origin, professor = run.private_state['roles']['origin'], run.private_state['professor']
    call(db, owner, run, 'investigate', client, actor=origin, topic='SOURCE')
    out = call(db, owner, run, 'investigate', client, actor=professor, topic='VERIFY')
    assert any(i['id'] == 'F' and i['confirmed'] for i in out['information'])
    call(db, owner, run, 'investigate', client, actor=origin, topic='RUMOR')
    with pytest.raises(HTTPException):
        call(db, owner, run, 'investigate', client, actor=origin, topic='RUMOR')
    db.rollback()
    run.intervention_opened_at = datetime.now(timezone.utc) - timedelta(seconds=301)
    db.commit()
    out = call(db, owner, run, 'intervene', choice='PUBLISH_FACT')
    assert out['interventions'][0]['elapsed_seconds'] >= 300
    for tick in range(2, 10):
        out = call(db, owner, run, 'advance', client)
        assert out['current_tick'] == tick
        if tick in (4, 7):
            out = call(db, owner, run, 'intervene', choice='WATCH')
    assert out['status'] == 'completed'
    assert {'CHAPTER1_CLEAR', 'FIRST_SENTENCE', 'INDECISIVE'} <= {a['id'] for a in out['achievements']}
    assert service.current(db, owner) == out
    with pytest.raises(HTTPException):
        call(db, owner, run, 'intervene', choice='WATCH')
    assert 'F' not in next(i for i in client.calls if str(i.agent.agent_id) == origin).rumor_context['information']


def test_http_contract(setup):
    db, owner, run = setup
    def session():
        yield db
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[require_user_role] = lambda: owner
    app.dependency_overrides[get_agent_runtime] = lambda: runtime()
    try:
        with TestClient(app) as client:
            assert client.get('/v1/challenges/rumor/current').json()['data']['id'] == str(run.id)
            path = f'/v1/challenges/rumor/{run.id}'
            assert client.post(path + '/advance', json={}).status_code == 422
            assert client.post(path + '/advance', json=payload(run)).status_code == 200
            assert client.get(path).json()['data']['current_tick'] == 1
            assert client.post(path + '/intervene', json=payload(run, choice='PUBLISH_FACT')).status_code == 422
            db.rollback()
            run.pending = {'request_id': str(uuid4()), 'fingerprint': 'old-server'}
            db.commit()
            recovered = client.post(path + '/recover', json=payload(run))
            assert recovered.status_code == 200
            assert recovered.json()['data']['busy'] is False
            assert recovered.json()['data']['current_tick'] == 1
            app.dependency_overrides[require_user_role] = lambda: User(id=uuid4())
            assert client.get(path).status_code == 404
            assert client.post(path + '/recover', json=payload(run)).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_concurrent_reservation_and_interrupted_execution(setup, engine):
    db, owner, run = setup
    started, release = Event(), Event()
    class BlockingClient(ChapterClient):
        def generate(self, inp):
            started.set()
            assert release.wait(10)
            return super().generate(inp)
    client, request = BlockingClient(), payload(run)
    def first():
        with Session(engine) as session:
            return service.command(session, owner, run.id, 'advance', request, runtime(client))
    with ThreadPoolExecutor() as pool:
        future = pool.submit(first)
        assert started.wait(10)
        with Session(engine) as other:
            with pytest.raises(HTTPException) as error:
                service.command(other, owner, run.id, 'advance', request, runtime(client))
            assert error.value.status_code == 409
        release.set()
        out = future.result(timeout=15)
    assert out['current_tick'] == 1 and len(client.calls) == 5
    db.expire_all()
    run = db.get(RumorChallengeRun, run.id)
    call(db, owner, run, 'intervene', choice='WATCH')
    class BrokenRuntime:
        calls = 0
        def run(self, inp):
            self.calls += 1
            raise RuntimeError('transport interrupted')
    broken, request = BrokenRuntime(), payload(run)
    with pytest.raises(HTTPException) as error:
        service.command(db, owner, run.id, 'advance', request, broken)
    assert error.value.status_code == 503
    assert service.response(db, service.owned(db, run.id, owner))['busy'] is False
    out = service.command(db, owner, run.id, 'advance', request, runtime())
    assert out['current_tick'] == 2
    assert service.command(db, owner, run.id, 'advance', request, broken) == out


def test_good_ending_through_actual_runtime_testimony(setup):
    db, owner, run = setup
    witness = run.private_state['roles']['witness']
    origin = run.private_state['roles']['origin']
    listeners = [run.private_state['roles'][r] for r in ('origin', 'exaggerator', 'believer')]
    client = ChapterClient()
    for tick in range(1, 10):
        client.plans = {}
        if tick <= 3:
            listener = listeners[tick - 1]
            client.plans = {witness: (listener, 'TESTIFY', 'F'), listener: (witness, None, None)}
            # The listener reciprocates TALK without transmitting information.
        out = call(db, owner, run, 'advance', client)
        if tick == 1:
            call(db, owner, run, 'investigate', client, actor=run.private_state['professor'], topic='VERIFY')
        if tick in (1, 4, 7):
            call(db, owner, run, 'intervene', choice='WATCH')
    assert out['grade'] == 'GOOD'
    assert out['chapter_record']['chapter'] == 1
    assert 'AHEAD_OF_RUMOR' in {a['id'] for a in out['achievements']}
    assert run.private_state['knowledge'][origin]['F'] == witness


def test_bad_ending_reached_by_real_transmissions_and_clear_is_still_awarded(setup):
    db, owner, run = setup
    origin = run.private_state['roles']['origin']
    targets = [run.private_state['roles'][r] for r in ('witness', 'subject')]
    client = ChapterClient()
    for tick in range(1, 10):
        client.plans = {}
        if tick <= 2:
            target = targets[tick - 1]
            client.plans = {origin: (target, 'TRANSFER', 'R0'), target: (origin, 'TRANSFER', 'R0')}
        out = call(db, owner, run, 'advance', client)
        if tick in (1, 4, 7):
            call(db, owner, run, 'intervene', choice='WATCH')
    assert out['grade'] == 'BAD' and out['school_spread']
    assert 'CHAPTER1_CLEAR' in {a['id'] for a in out['achievements']}


def test_chapter_cannot_be_advanced_through_general_simulation_services(setup):
    import asyncio
    from app.domain.models import Simulation
    from app.services.manual_tick import advance_manual_tick, TickAlreadyRunningError
    from app.services.night_transition import skip_night, NightSkipNotAllowedError
    from app.services.simulations import update_simulation_status, InvalidSimulationStatusTransitionError
    db, owner, run = setup
    simulation = db.get(Simulation, run.simulation_id)
    with pytest.raises(TickAlreadyRunningError):
        asyncio.run(advance_manual_tick(db, simulation, runtime=runtime()))
    with pytest.raises(NightSkipNotAllowedError):
        skip_night(db, simulation)
    with pytest.raises(InvalidSimulationStatusTransitionError):
        update_simulation_status(db, simulation, 'running')
    assert simulation.current_tick == 0


def test_invalid_information_and_forged_source_do_not_update_chapter(setup):
    db, owner, run = setup
    a, b = [run.private_state['roles'][r] for r in ('origin', 'subject')]
    client = ChapterClient({a: (b, 'TESTIFY', 'F'), b: (a, 'TRANSFER', 'F')})
    out = call(db, owner, run, 'advance', client)
    assert not out['history']
    assert 'F' not in run.private_state['knowledge'][a]
    old_revision = run.revision
    with pytest.raises(HTTPException) as error:
        service.command(db, owner, run.id, 'intervene', dict(payload(run, choice='WATCH'), expected_revision=0))
    assert error.value.status_code == 409 and run.revision == old_revision


@pytest.mark.parametrize('failure', ['timeout', 'db_flush', 'db_statement', 'commit_before', 'commit_after'])
def test_failed_command_is_atomic_and_same_request_can_resume(setup, monkeypatch, failure):
    from app.domain.models import AgentState, Simulation
    db, owner, run = setup
    origin, subject = [run.private_state['roles'][r] for r in ('origin', 'subject')]
    client = ChapterClient({origin: (subject, 'TRANSFER', 'R1'), subject: (origin, 'TESTIFY', 'F')})
    request = payload(run)
    before = service.response(db, run)
    relation = db.scalar(select(Relationship).where(Relationship.source_agent_id == UUID(origin), Relationship.target_agent_id == UUID(subject)))
    trust_before = relation.trust
    states = {str(a.agent_id): (a.hunger, a.fatigue, a.stress, a.satisfaction) for a in db.scalars(
        select(AgentState).where(AgentState.agent_id.in_([UUID(a) for a in run.private_state['knowledge']])))}
    original_flush, original_commit = db.flush, db.commit
    if failure == 'timeout':
        class TimeoutRuntime:
            def run(self, inp):
                raise TimeoutError('simulated')
        chosen_runtime = TimeoutRuntime()
    else:
        chosen_runtime = runtime(client)
        if failure in ('db_flush', 'db_statement'):
            def fail_flush(*args, **kwargs):
                if db.new:  # fail after command acquired the row lock
                    if failure == 'db_statement':
                        from sqlalchemy import text
                        db.execute(text('SELECT 1 / 0'))
                    raise RuntimeError('simulated flush failure')
                return original_flush(*args, **kwargs)
            monkeypatch.setattr(db, 'flush', fail_flush)
        else:
            def fail_commit():
                if failure == 'commit_after':
                    original_commit()
                raise RuntimeError('simulated commit failure')
            monkeypatch.setattr(db, 'commit', fail_commit)
    if failure != 'commit_after':
        with pytest.raises(HTTPException) as error:
            service.command(db, owner, run.id, 'advance', request, chosen_runtime)
        assert error.value.status_code == 503
    else:
        out = service.command(db, owner, run.id, 'advance', request, chosen_runtime)
        assert out['current_tick'] == 1
    monkeypatch.setattr(db, 'flush', original_flush)
    monkeypatch.setattr(db, 'commit', original_commit)
    run = service.owned(db, run.id, owner)
    out = service.response(db, run)
    if failure != 'commit_after':
        assert out['revision'] == before['revision'] and out['current_tick'] == 0 and not out['busy']
        assert db.get(Simulation, run.simulation_id).current_tick == 0
        after_states = {str(a.agent_id): (a.hunger, a.fatigue, a.stress, a.satisfaction) for a in db.scalars(
            select(AgentState).where(AgentState.agent_id.in_([UUID(a) for a in run.private_state['knowledge']])))}
        assert after_states == states
        db.refresh(relation)
        assert relation.trust == trust_before
    out = service.command(db, owner, run.id, 'advance', request, runtime(client))
    assert out['revision'] == before['revision'] + 1 and out['current_tick'] == 1
    db.refresh(relation)
    assert relation.trust == trust_before + 1
    count = len(client.calls)
    assert service.command(db, owner, run.id, 'advance', request, runtime(client)) == out
    assert len(client.calls) == count
    transfers = [h for h in out['history'] if h['kind'] == 'TRANSFER']
    if failure != 'timeout':
        assert len(transfers) == 1


def test_saved_orphan_reservation_can_be_recovered_without_llm_or_progress(setup):
    db, owner, run = setup
    request = payload(run)
    run.pending = {'request_id': request['request_id'], 'fingerprint': 'interrupted-process'}
    db.commit()
    before = run.revision
    out = service.recover(db, owner, run.id, request)
    assert not out['busy'] and out['revision'] == before and out['current_tick'] == 0
    assert service.recover(db, owner, run.id, request) == out
    out = service.command(db, owner, run.id, 'advance', request, runtime())
    assert out['current_tick'] == 1


def test_recovery_cannot_interrupt_active_command(setup, engine):
    db, owner, run = setup
    started, release = Event(), Event()
    class BlockingClient(ChapterClient):
        def generate(self, inp):
            started.set()
            assert release.wait(10)
            return super().generate(inp)
    request = payload(run)
    def first():
        with Session(engine) as session:
            return service.command(session, owner, run.id, 'advance', request, runtime(BlockingClient()))
    with ThreadPoolExecutor() as pool:
        future = pool.submit(first)
        assert started.wait(10)
        with Session(engine) as other:
            with pytest.raises(HTTPException) as error:
                service.recover(other, owner, run.id, request)
            assert error.value.status_code == 409
        release.set()
        assert future.result(timeout=15)['current_tick'] == 1


def test_process_exit_releases_lock_and_rolls_back_uncommitted_tick(setup, engine):
    import subprocess
    import sys
    db, owner, run = setup
    request = payload(run)
    child = """
import json, os, sys
from types import SimpleNamespace
from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.services.rumor_challenge import command
class CrashRuntime:
    def run(self, inp):
        os._exit(23)
with Session(create_engine(os.environ['TEST_DATABASE_URL'])) as db:
    command(db, SimpleNamespace(id=UUID(sys.argv[1])), UUID(sys.argv[2]), 'advance', json.loads(sys.argv[3]), CrashRuntime())
"""
    result = subprocess.run([sys.executable, '-c', child, str(owner.id), str(run.id), __import__('json').dumps(request)],
                            timeout=15, capture_output=True)
    assert result.returncode == 23
    db.expire_all()
    out = service.response(db, service.owned(db, run.id, owner))
    assert out['revision'] == 0 and out['current_tick'] == 0 and not out['busy']
    out = service.command(db, owner, run.id, 'advance', request, runtime())
    assert out['current_tick'] == 1 and out['revision'] == 1


def test_llm_timeout_fallbacks_return_error_without_consuming_tick(setup):
    from app.simulation.agent_runtime import LLMInvocationError
    db, owner, run = setup
    class TimedOutClient:
        def generate(self, inp):
            raise LLMInvocationError('simulated timeout')
    request = payload(run)
    with pytest.raises(HTTPException) as error:
        service.command(db, owner, run.id, 'advance', request, runtime(TimedOutClient()))
    assert error.value.status_code == 503
    out = service.response(db, service.owned(db, run.id, owner))
    assert out['revision'] == 0 and not out['busy'] and not out['observations']
    assert service.command(db, owner, run.id, 'advance', request, runtime())['current_tick'] == 1


@pytest.mark.parametrize('repeat_topic', ['VERIFY', 'COMPARE'])
def test_investigation_achievements_reachable_with_actual_round_budgets(setup, repeat_topic):
    db, owner, run = setup
    client = ChapterClient()
    origin, exaggerator, believer = [run.private_state['roles'][r] for r in ('origin', 'exaggerator', 'believer')]
    call(db, owner, run, 'advance', client)
    call(db, owner, run, 'investigate', client, actor=origin, topic='SOURCE')
    call(db, owner, run, 'investigate', client, actor=origin, topic='RUMOR')
    call(db, owner, run, 'investigate', client, actor=exaggerator, topic='RUMOR')
    run.intervention_opened_at = datetime.now(timezone.utc) - timedelta(seconds=301)
    db.commit()
    call(db, owner, run, 'intervene', choice='WATCH')
    for tick in range(2, 10):
        out = call(db, owner, run, 'advance', client)
        if tick == 4:
            call(db, owner, run, 'investigate', client, actor=origin, topic='COMPARE', statement_indices=[1, 2])
            call(db, owner, run, 'investigate', client, actor=run.private_state['professor'], topic='VERIFY')
            call(db, owner, run, 'investigate', client, actor=believer, topic='RUMOR')
            call(db, owner, run, 'intervene', choice='PUBLISH_FACT')
        elif tick == 7:
            call(db, owner, run, 'investigate', client, actor=run.private_state['professor'],
                 topic=repeat_topic, statement_indices=[1, 2] if repeat_topic == 'COMPARE' else [])
            call(db, owner, run, 'intervene', choice='WATCH')
    earned = {a['id'] for a in out['achievements']}
    assert {'CHAPTER1_CLEAR', 'FIRST_SENTENCE', 'THREE_RUMORS', 'HEARD_AND_SEEN', 'INDECISIVE'} <= earned
    # An announcement without actual student acceptance/testimony is not a win.
    assert out['grade'] == 'MIXED' and out['misinformed_count'] == 3


def test_action_achievements_reachable_through_actual_transmission_and_retraction(setup):
    db, owner, run = setup
    client = ChapterClient()
    origin, exaggerator, believer, witness = [run.private_state['roles'][r] for r in ('origin', 'exaggerator', 'believer', 'witness')]
    call(db, owner, run, 'advance', client)
    call(db, owner, run, 'investigate', client, actor=origin, topic='RUMOR')
    call(db, owner, run, 'intervene', choice='SHARE', target=believer, information_id='R0')
    for tick in range(2, 10):
        client.plans = {}
        if tick == 2:
            client.plans = {believer: (origin, 'TRANSFER', 'R1'), origin: (believer, None, None)}
        elif tick == 5:
            client.plans = {origin: (exaggerator, 'CORRECT', 'F'), exaggerator: (origin, None, None)}
        elif tick == 8:
            client.plans = {witness: (believer, 'TESTIFY', 'F'), believer: (witness, None, None)}
        out = call(db, owner, run, 'advance', client)
        if tick == 4:
            call(db, owner, run, 'investigate', client, actor=run.private_state['professor'], topic='VERIFY')
            call(db, owner, run, 'intervene', choice='PUBLISH_FACT')
        elif tick == 7:
            call(db, owner, run, 'intervene', choice='REQUEST_TESTIMONY', target=witness, information_id='F')
    assert out['grade'] == 'GOOD'
    assert {'CHAPTER1_CLEAR', 'FAN_THE_FLAME', 'SELF_CORRECTION', 'SILENT_WITNESS', 'AHEAD_OF_RUMOR'} <= {a['id'] for a in out['achievements']}
    correction_input = next(i for i in client.calls if str(i.agent.agent_id) == origin and i.tick_number == 5)
    assert any(h['target'] == exaggerator for h in correction_input.rumor_context['my_transmissions'])


@pytest.mark.parametrize('choice,role,kind', [('REQUEST_TESTIMONY', 'witness', 'TESTIFY'), ('REQUEST_CORRECTION', 'origin', 'CORRECT')])
def test_request_followed_by_refusal_does_not_award_actual_action(setup, choice, role, kind):
    db, owner, run = setup
    client = ChapterClient()
    call(db, owner, run, 'advance', client)
    call(db, owner, run, 'investigate', client, actor=run.private_state['professor'], topic='VERIFY')
    call(db, owner, run, 'intervene', choice=choice, target=run.private_state['roles'][role], information_id='F')
    out = call(db, owner, run, 'advance', client)
    assert out['interventions'][0]['choice'] == choice
    assert not any(h['kind'] == kind for h in out['history'])
    assert out['misinformed_count'] == 3


if __name__ == '__main__':
    # E2E 전용 진입점: 테스트 DB 환경 변수와 CORS 설정을 지정해 실행한다.
    import os
    import uvicorn
    app.dependency_overrides[get_agent_runtime] = lambda: runtime()

    @app.get('/health/e2e-runtime')
    def e2e_runtime_health():
        return {'runtime': 'mock'}

    uvicorn.run(app, host=os.getenv('E2E_API_HOST', '127.0.0.1'), port=8001)
