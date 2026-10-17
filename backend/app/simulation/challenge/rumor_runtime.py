"""개인별 정보만 Runtime에 주입하고 일반 조회 경로에는 내부 설명을 남기지 않는다."""
from copy import deepcopy
from app.simulation.agent_runtime import ActionType, RuntimeStatus
from app.simulation.challenge.rumor import agent_context


class RumorRuntime:
    def __init__(self, runtime, state, *, inquiry=None):
        self.runtime = runtime
        self.state = deepcopy(state)
        self.inquiry = inquiry
        self.raw_results = {}
        self.event_ids = {}

    def run(self, runtime_input):
        actor = str(runtime_input.agent.agent_id)
        self.event_ids[actor] = str(runtime_input.schedule.event_id)
        context = agent_context(self.state, actor)
        if self.inquiry:
            context['inquiry'] = self.inquiry
        scoped = runtime_input.model_copy(update={'memories': [], 'rumor_context': context})
        result = self.runtime.run(scoped)
        self.raw_results[actor] = result.model_dump(mode='json')
        # 일반 Agent Inspector/대화/Runtime 조회로 비공개 근거가 새지 않게 한다.
        intent = result.intent.model_copy(deep=True)
        intent.rumor_acts = []
        intent.memory_candidates = []
        intent.utterance = None
        intent.motivation_summary = '조정관이 학생의 행동을 관찰했습니다.'
        intent.decision_explanation.influencing_factors = []
        for alternative in intent.decision_explanation.alternatives:
            alternative.description = '현재 상황을 고려한 행동입니다.'
        return result.model_copy(update={'intent': intent, 'failure_reason': '판단을 보류했습니다.' if result.failure_reason else None})


def executed_acts(results, raw_results, *, inquiry=None):
    """충돌 해소 뒤 실제 결과와 원시 구조화 결과를 대조한다."""
    acts = []
    by_actor = {str(r.agent_id): r for r in results}
    for actor, raw in raw_results.items():
        result = by_actor.get(actor)
        if result is None or result.status != RuntimeStatus.PROPOSED:
            continue
        for act in raw['intent'].get('rumor_acts', []):
            if inquiry:
                if (act['kind'] != 'ANSWER' or act['target'] != 'player'
                        or actor != inquiry['actor']
                        or result.intent.action_type != ActionType.PARTICIPATE_EVENT
                        or str(result.intent.related_event_id) != inquiry['event_id']):
                    continue
            else:
                target = by_actor.get(act['target'])
                if (act['kind'] == 'ANSWER' or result.intent.action_type != ActionType.TALK
                        or str(result.intent.target_agent_id) != act['target'] or target is None
                        or target.status != RuntimeStatus.PROPOSED
                        or target.intent.action_type != ActionType.TALK
                        or str(target.intent.target_agent_id) != actor):
                    continue
            acts.append(dict(actor=actor, **act))
    return acts
