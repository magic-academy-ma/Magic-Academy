from contextlib import contextmanager
from contextvars import ContextVar

import pytest

from app.core import tracing
from app.core.config import Settings
from app.simulation.agent_runtime import AgentRuntime, LLMInvocationError, MockLLMClient
from app.simulation.llm_quota import LLMQuota
from tests.test_agent_runtime_graph import (
    SequenceLLMClient,
    invalid_response,
    make_runtime_input,
    valid_response,
)


def test_disabled_and_missing_keys_do_not_create_client(monkeypatch):
    calls = []
    def forbidden(settings):
        calls.append(settings)
        raise AssertionError('SDK must not initialize')
    monkeypatch.setattr(tracing, '_create_client', forbidden)
    for enabled in (False, True):
        tracing.configure_tracing(Settings(_env_file=None, langfuse_enabled=enabled))
        with tracing.observation('test') as span:
            span.update(metadata={'status': 'completed'})
        tracing.shutdown_tracing()
    assert calls == []


class Recorder:
    def __init__(self):
        self.spans = []
        self.current = ContextVar('test_parent', default=None)

    @contextmanager
    def start_as_current_observation(self, **fields):
        record = {'fields': fields, 'updates': [], 'parent': self.current.get()}
        self.spans.append(record)
        token = self.current.set(record)
        class Span:
            def update(self, **kwargs):
                record['updates'].append(kwargs)
        try:
            yield Span()
        finally:
            self.current.reset(token)


@pytest.fixture
def recorder(monkeypatch):
    client = Recorder()
    monkeypatch.setattr(tracing, '_client', client)
    return client


def metadata(record):
    result = dict(record['fields'].get('metadata') or {})
    for update in record['updates']:
        result.update(update.get('metadata', {}))
    return result


@pytest.mark.parametrize('mode', ['success', 'retry', 'fallback', 'skipped', 'quota', 'llm_error'])
def test_runtime_outcomes_and_privacy(recorder, mode):
    inp = make_runtime_input(active=mode != 'skipped')
    outcomes = [valid_response(inp)]
    if mode == 'retry':
        outcomes.insert(0, invalid_response(inp))
    if mode == 'fallback':
        outcomes = [invalid_response(inp)] * 2
    if mode == 'llm_error':
        outcomes = [LLMInvocationError('private-input-secret')] * 2
    quota = LLMQuota(1)
    if mode == 'quota':
        quota.try_consume()
    runtime = AgentRuntime(SequenceLLMClient(outcomes), llm_quota=quota if mode == 'quota' else None)
    with tracing.observation('tick'):
        result = runtime.run(inp)
    agent = next(s for s in recorder.spans if s['fields']['name'] == 'agent.runtime')
    assert agent['parent'] is recorder.spans[0]
    assert metadata(agent)['runtime_status'] == result.status.value
    assert metadata(agent)['retry_count'] == result.retry_count
    assert 'private-input-secret' not in str(recorder.spans)
    assert 'motivation_summary' not in str(recorder.spans)
    if mode in ('fallback', 'retry'):
        assert any(metadata(s).get('failure_reason') == 'output_validation_failed' for s in recorder.spans)
    if mode == 'quota':
        assert any(metadata(s).get('failure_reason') == 'quota_exceeded' for s in recorder.spans)


def test_recording_failure_does_not_change_result(monkeypatch):
    inp = make_runtime_input()
    expected = AgentRuntime(MockLLMClient()).run(inp)
    class Broken:
        def start_as_current_observation(self, **kwargs):
            raise RuntimeError('private-key')
    monkeypatch.setattr(tracing, '_client', Broken())
    assert AgentRuntime(MockLLMClient()).run(inp) == expected


@pytest.mark.parametrize("cache_tokens", [None, (0, 0), (3, 4)])
def test_real_sdk_exports_parent_hierarchy_usage_and_no_raw_data(monkeypatch, cache_tokens):
    from types import SimpleNamespace
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from app.simulation.anthropic_llm_client import AnthropicLLMClient
    from tests.test_anthropic_llm_client import FakeAnthropic
    exporter = InMemorySpanExporter()
    monkeypatch.setattr(tracing, '_create_transport', lambda settings: exporter)
    monkeypatch.setattr(tracing, '_client', None)
    tracing.configure_tracing(Settings(_env_file=None, langfuse_enabled=True,
        langfuse_public_key=f'pk-local-tracing-test-{cache_tokens}', langfuse_secret_key='sk-local-tracing-test',
        langfuse_base_url='http://localhost:1'))
    inp = make_runtime_input()
    inp.memories.append({'content': 'private-memory-do-not-export'})
    expected_usage = {'input': 12, 'output': 5}
    provider_usage = {'input_tokens': 12, 'output_tokens': 5}
    if cache_tokens is not None:
        cache_fields = dict(zip(
            ('cache_read_input_tokens', 'cache_creation_input_tokens'), cache_tokens
        ))
        provider_usage.update(cache_fields)
        expected_usage.update(cache_fields)
    client = AnthropicLLMClient(model='test-model', max_tokens=100,
        client=FakeAnthropic(SimpleNamespace(parsed_output=valid_response(inp),
            usage=SimpleNamespace(**provider_usage))))
    with tracing.observation('tick'):
        AgentRuntime(client).run(inp)
        with pytest.raises(ValueError):
            with tracing.observation('failure'):
                raise ValueError('private-exception-message')
    tracing.shutdown_tracing()
    spans = exporter.get_finished_spans()
    names = {s.name: s for s in spans}
    assert {'tick', 'agent.runtime', 'llm.attempt', 'anthropic.generate'} <= names.keys()
    assert names['agent.runtime'].parent.span_id == names['tick'].context.span_id
    assert names['anthropic.generate'].parent.span_id == names['llm.attempt'].context.span_id
    assert len({s.context.trace_id for s in spans}) == 1
    assert 'private-memory-do-not-export' not in str([s.attributes for s in spans])
    assert 'private-exception-message' not in str([s.attributes for s in spans])
    import json
    usage = json.loads(names['anthropic.generate'].attributes['langfuse.observation.usage_details'])
    assert usage == expected_usage
    assert all(not span.events for span in spans)
    assert all("public_key" not in (span.instrumentation_scope.attributes or {}) for span in spans)


@pytest.mark.parametrize('enabled,url', [('', ''), ('invalid', ''), (True, 'file:///tmp/a'), (True, 'http://['), (True, 'https://user:pass@example.com')])
def test_invalid_settings_fail_closed(monkeypatch, enabled, url):
    monkeypatch.setattr(tracing, '_client', None)
    def forbidden(settings):
        pytest.fail('Invalid config must not initialize SDK')
    monkeypatch.setattr(tracing, '_create_client', forbidden)
    settings = Settings(_env_file=None, langfuse_enabled=enabled,
        langfuse_public_key='pk', langfuse_secret_key='sk', langfuse_base_url=url)
    tracing.configure_tracing(settings)
    assert tracing._client is None


def test_settings_read_dotenv_and_environment(tmp_path, monkeypatch):
    env = tmp_path / '.env'
    env.write_text('LANGFUSE_ENABLED=true\nLANGFUSE_PUBLIC_KEY=pk-file\nLANGFUSE_SECRET_KEY=sk-file\nLANGFUSE_BASE_URL=https://example.com\n')
    settings = Settings(_env_file=env)
    assert settings.langfuse_enabled
    assert settings.langfuse_public_key == 'pk-file'
    monkeypatch.setenv('LANGFUSE_ENABLED', 'false')
    assert not Settings(_env_file=env).langfuse_enabled
    assert 'sk-file' not in repr(settings)


def test_initialize_once_and_shutdown_even_if_flush_fails(monkeypatch):
    calls = []
    class Client:
        def flush(self):
            calls.append('flush')
            raise RuntimeError('private-error')
        def shutdown(self):
            calls.append('shutdown')
    monkeypatch.setattr(tracing, '_client', None)
    monkeypatch.setattr(tracing, '_create_client', lambda settings: calls.append('init') or Client())
    settings = Settings(_env_file=None, langfuse_enabled=True,
        langfuse_public_key='pk', langfuse_secret_key='sk', langfuse_base_url='https://example.com')
    tracing.configure_tracing(settings)
    tracing.configure_tracing(settings)
    tracing.shutdown_tracing()
    assert calls == ['init', 'flush', 'shutdown']


async def test_tick_parallel_agent_context_isolation(recorder):
    from uuid import UUID
    from app.services.runtime_orchestrator import RuntimeOrchestrator
    from app.services.runtime_results import InMemoryRuntimeResultSink
    from app.simulation.tick_engine import TickEngine, WorldSnapshot, TickAgent, TickEvent, AgentType
    inputs = [make_runtime_input() for _ in range(5)]
    for i, inp in enumerate(inputs, 1):
        inp.agent.agent_id = UUID(f'00000000-0000-0000-0000-{i:012d}')
    orchestrator = RuntimeOrchestrator(AgentRuntime(MockLLMClient()), InMemoryRuntimeResultSink())
    async def batch(agents, event, snapshot):
        return {str(r.agent_id): r for r in orchestrator.run_batch(inputs).results}
    engine = TickEngine(batch)
    result = await engine.run_tick(
        [TickAgent(str(i.agent.agent_id), AgentType.STUDENT, True) for i in inputs],
        TickEvent('event', 'class', set()), WorldSnapshot('sim', 3))
    assert result.status == 'completed'
    agents = [s for s in recorder.spans if s['fields']['name'] == 'agent.runtime']
    assert len(agents) == 5
    assert len({metadata(s)['agent_id'] for s in agents}) == 5
    root = recorder.spans[0]
    assert all(s['parent'] is root for s in agents)
    attempts = [s for s in recorder.spans if s['fields']['name'] == 'llm.attempt']
    assert len(attempts) == 5
    assert all(s['parent'] in agents for s in attempts)
    assert recorder.current.get() is None


def test_exit_and_update_failure_preserve_application_exception(monkeypatch):
    class BrokenSpan:
        def update(self, **kwargs):
            raise RuntimeError('export-secret')
    class BrokenManager:
        def __enter__(self):
            return BrokenSpan()
        def __exit__(self, *args):
            assert args == (None, None, None)
            raise RuntimeError('export-secret')
    class BrokenClient:
        def start_as_current_observation(self, **kwargs):
            return BrokenManager()
    monkeypatch.setattr(tracing, '_client', BrokenClient())
    with pytest.raises(ValueError, match='original'):
        with tracing.observation('tick'):
            raise ValueError('original')


def test_mock_never_opens_network(recorder, monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        pytest.fail('Mock runtime opened network')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    result = AgentRuntime(MockLLMClient()).run(make_runtime_input())
    assert result.status.value == 'PROPOSED'
    assert not any(s['fields']['as_type'] == 'generation' for s in recorder.spans)
    assert any(metadata(s).get('provider') == 'mock' for s in recorder.spans)


async def test_tick_rollback_contract_survives_telemetry_failure(monkeypatch):
    from app.simulation.tick_engine import (
        TickEngine, WorldSnapshot, TickAgent, TickEvent, AgentType,
        RuntimeExecutionError, TickRollbackError,
    )
    class BrokenClient:
        def start_as_current_observation(self, **kwargs):
            raise RuntimeError('transport-down')
    monkeypatch.setattr(tracing, '_client', BrokenClient())
    async def fail(*args):
        raise RuntimeExecutionError('expected-runtime-failure')
    engine = TickEngine(fail)
    with pytest.raises(TickRollbackError) as error:
        await engine.run_tick([TickAgent('a', AgentType.STUDENT, True)],
            TickEvent('event', 'class', set()), WorldSnapshot('sim', 1))
    assert isinstance(error.value.__cause__, RuntimeExecutionError)
    assert not engine._running


def test_initialization_failure_is_safe_and_does_not_log_secret(monkeypatch, caplog):
    monkeypatch.setattr(tracing, '_client', None)
    def fail(settings):
        raise RuntimeError('private-langfuse-key')
    monkeypatch.setattr(tracing, '_create_client', fail)
    tracing.configure_tracing(Settings(_env_file=None, langfuse_enabled=True,
        langfuse_public_key='pk', langfuse_secret_key='private-langfuse-key',
        langfuse_base_url='https://example.com'))
    assert tracing._client is None
    assert 'private-langfuse-key' not in caplog.text


def test_sdk_export_transport_failure_keeps_runtime_result(monkeypatch):
    from opentelemetry.sdk.trace.export import SpanExporter
    class FailingExporter(SpanExporter):
        def export(self, spans):
            raise ConnectionError('simulated-export-failure')
    monkeypatch.setattr(tracing, '_create_transport', lambda settings: FailingExporter())
    monkeypatch.setattr(tracing, '_client', None)
    inp = make_runtime_input()
    expected = AgentRuntime(MockLLMClient()).run(inp)
    tracing.configure_tracing(Settings(_env_file=None, langfuse_enabled=True,
        langfuse_public_key='pk-failing-export-test', langfuse_secret_key='sk-fake',
        langfuse_base_url='http://localhost:1'))
    assert AgentRuntime(MockLLMClient()).run(inp) == expected
    tracing.shutdown_tracing()


async def test_manual_tick_trace_uses_refreshed_tick_under_concurrent_execution(recorder):
    import asyncio
    from types import SimpleNamespace
    from app.simulation.tick_engine import TickEngine, TickEvent, WorldSnapshot

    lock = asyncio.Lock()
    committed = SimpleNamespace(current_tick=5)

    @tracing.trace_tick
    async def advance(db, simulation):
        async with lock:
            # Both callers hold stale pre-lock objects; the locked refresh is authoritative.
            await asyncio.sleep(0)
            simulation.current_tick = committed.current_tick
            current_tick = simulation.current_tick + 1
            async def unused_runtime(*args):
                pytest.fail('Empty participant tick must not call runtime')
            await TickEngine(unused_runtime).run_tick(
                [], TickEvent('event', 'class', set()),
                WorldSnapshot(simulation.id, current_tick),
            )
            committed.current_tick = simulation.current_tick = current_tick
            return SimpleNamespace(current_tick=current_tick)

    results = await asyncio.gather(*(
        advance(None, SimpleNamespace(id='simulation', current_tick=0))
        for _ in range(2)
    ))
    roots = [s for s in recorder.spans if s['fields']['name'] == 'tick']
    engines = [s for s in recorder.spans if s['fields']['name'] == 'tick.engine']
    assert [r.current_tick for r in results] == [6, 7]
    assert [metadata(s)['tick_number'] for s in roots] == [6, 7]
    assert all('tick_number' not in s['fields']['metadata'] for s in roots)
    assert all(metadata(s)['status'] == 'completed' for s in roots)
    assert all(metadata(s)['tick_number'] == metadata(s['parent'])['tick_number'] for s in engines)
    assert recorder.current.get() is None


async def test_manual_tick_lock_rejection_does_not_read_unlocked_tick(recorder):
    from types import SimpleNamespace
    from app.services.manual_tick import advance_manual_tick, TickAlreadyRunningError

    class UnlockedSimulation:
        id = 'simulation'
        @property
        def current_tick(self):
            pytest.fail('Tracing must not read current_tick before the DB lock')

    db = SimpleNamespace(scalar=lambda statement: False)
    with pytest.raises(TickAlreadyRunningError):
        await advance_manual_tick(db, UnlockedSimulation(), runtime=AgentRuntime(MockLLMClient()))
    root = recorder.spans[0]
    assert metadata(root)['status'] == 'failed'
    assert 'tick_number' not in metadata(root)


@pytest.mark.parametrize('mutate_tick', [False, True])
async def test_failed_manual_tick_does_not_publish_an_uncommitted_tick(recorder, mutate_tick):
    from types import SimpleNamespace
    error = ValueError('original failure')
    simulation = SimpleNamespace(id='simulation', current_tick=0)

    @tracing.trace_tick
    async def advance(db, simulation):
        if mutate_tick:
            simulation.current_tick = 9
        raise error

    with pytest.raises(ValueError) as caught:
        await advance(None, simulation)
    assert caught.value is error
    assert metadata(recorder.spans[0])['status'] == 'failed'
    assert 'tick_number' not in metadata(recorder.spans[0])


async def test_trace_tick_preserves_invalid_call_contract(recorder):
    @tracing.trace_tick
    async def advance(db, simulation):
        pytest.fail('Invalid call must not enter the function')

    with pytest.raises(TypeError):
        await advance()
    assert recorder.spans == []
