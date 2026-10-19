"""CHAPTER 1: 검증된 정보 기록으로만 변경하는 순수 상태 전이."""
from copy import deepcopy
import random
from dataclasses import asdict
from app.simulation.challenge.record import ChapterGrade, ChapterRecord, InterventionRecord, is_indecisive

# 임시값: 플레이테스트 후 조정.
ROUND_COUNT = 3
TICKS_PER_ROUND = 3
TOTAL_TICKS = ROUND_COUNT * TICKS_PER_ROUND
INQUIRIES_PER_ROUND = 3
SCHOOL_SPREAD_THRESHOLD = 5
SCHOOL_MISUNDERSTANDING_THRESHOLD = 3
INTERVENTION_TICKS = (1, 4, 7)
INFORMATION = {
    'R0': '수업 중 한 학생이 금지된 마법을 몰래 사용했다는 소문입니다.',
    'R1': '교수가 현장에서 잡아 징계한다는 소문입니다.',
    'R2': '그 학생이 퇴학당한다는 소문입니다.',
    'F': '교수가 허가한 안전한 보호마법 실습이었습니다. 금지 마법 사용도 징계도 퇴학도 없습니다.',
    'S': '제가 확인하지 않은 추측을 처음 이야기했습니다.',
}
NEXT_VARIANT = {'R0': 'R1', 'R1': 'R2'}
CHOICES = {'WATCH': '지켜보기', 'SHARE': '들은 정보 전달', 'REQUEST_TESTIMONY': '증언 요청',
           'REQUEST_CORRECTION': '정정 요청', 'PUBLISH_FACT': '확인 사실 공지'}
TOPICS = {'RUMOR': '들은 소문', 'SOURCE': '누구에게 들었나', 'OBSERVED': '직접 본 사실',
          'VERIFY': '사실 확인', 'COMPARE': '진술 비교'}
ACHIEVEMENTS = dict(zip(
    ('CHAPTER1_CLEAR', 'FIRST_SENTENCE', 'HEARD_AND_SEEN', 'FAN_THE_FLAME', 'SILENT_WITNESS',
     'THREE_RUMORS', 'AHEAD_OF_RUMOR', 'SELF_CORRECTION', 'INDECISIVE'),
    ('CHAPTER 1 클리어', '소문의 첫 문장', '들은 것과 본 것', '불씨를 키운 사람', '침묵을 깬 증인',
     '말이 말을 낳고', '소문보다 한발 먼저', '되돌리는 한마디', '우유부단하시네요')))


def initialize(students, professor, seed):
    if len(students) != 5 or len(set(students)) != 5 or professor in students:
        raise ValueError('학생 5명과 교수 1명이 필요합니다.')
    rng = random.Random(seed)
    shuffled = list(students)
    rng.shuffle(shuffled)
    roles = dict(zip(('subject', 'origin', 'exaggerator', 'witness', 'believer'), shuffled))
    knowledge = {a: {} for a in [*students, professor]}
    for role in ('subject', 'witness'):
        knowledge[roles[role]]['F'] = roles[role]
    knowledge[professor]['F'] = professor
    a, b, c = (roles[k] for k in ('origin', 'exaggerator', 'believer'))
    knowledge[a] = {'R0': a, 'S': a}
    knowledge[b] = {'R0': a, 'R1': a}
    knowledge[c] = {'R2': b}
    return dict(students=list(students), professor=professor, roles=roles,
                truth={'fact': 'F', 'misperception': rng.choice(('문틈으로 빛을 봄', '복도에서 경고음을 들음'))},
                motive=rng.choice(('갈등에 휘말리기 싫다', '친구에게 불이익이 갈까 걱정된다')),
                tick=0, knowledge=knowledge,
                fact_holders=[roles['subject'], roles['witness'], professor],
                unresolved={x: [i for i in knowledge[x] if i.startswith('R')] for x in students},
                reached=[a, b, c], school_spread_tick=None,
                history=[dict(kind='INITIAL', actor=a, target=b, information_id='R0', source_id=a, tick=0),
                         dict(kind='INITIAL', actor=b, target=c, information_id='R2', source_id=a, tick=0)],
                statements=[], heard=[], verified=[], compared_at=None, verified_at=None,
                interventions=[], inquiries={}, achievements=[], grade=None, ending=None,
                flame_links=[], flame=False, witness_spoke=False, corrected=False)


def _stamp(s):
    return len(s['history']) + len(s['statements']) + len(s['interventions'])


def agent_context(s, actor):
    known = s['knowledge'][actor]
    context = dict(incident_subject=s['roles']['subject'], information={i: dict(text=INFORMATION[i], source_id=source, confirmed=i == 'F', accepted=i == 'F' and actor in fact_holders(s))
                                for i, source in known.items()},
                   possible_distortions={NEXT_VARIANT[i]: dict(text=INFORMATION[NEXT_VARIANT[i]],
                                       source_id=source, derived_from=i, confirmed=False)
                                       for i, source in known.items() if i in NEXT_VARIANT},
                   requests=[x for x in s['interventions'] if x['target'] in (actor, 'all')])
    if actor == s['roles']['exaggerator']:
        context['my_perspective'] = '재미있는 이야기라 더 자극적으로 전하고 싶다. 사실 확인은 하지 않았다.'
    if actor == s['roles']['believer']:
        context['my_perspective'] = '들은 이야기를 사실로 믿고 있다. 직접 본 것은 아니다.'
    if actor == s['roles']['witness']:
        context['my_motive'] = s['motive']
    if actor == s['roles']['origin']:
        context['my_observation'] = s['truth']['misperception']
    context['my_transmissions'] = [dict(h) for h in s['history'] if h.get('actor') == actor
                                   and h['kind'] in ('INITIAL', 'TRANSFER', 'TESTIFY', 'CORRECT')]
    context['my_unresolved_rumors'] = [] if actor in fact_holders(s) else list(s['unresolved'].get(actor, []))
    context['fact_accepted'] = actor in fact_holders(s)
    if context['fact_accepted']:
        context['my_perspective'] = '보호마법 실습이었다는 사실을 알고 있다. 들은 소문과 사실을 구분한다.'
    return context


def investigate_answer(s, actor, topic, info):
    allowed = {'RUMOR': ('R0', 'R1', 'R2'), 'SOURCE': ('S', 'R0', 'R1', 'R2'),
               'VERIFY': ('F',), 'OBSERVED': ('F', 'S')}
    if info not in s['knowledge'].get(actor, {}) or info not in allowed.get(topic, ()):
        return False
    entry = dict(actor=actor, information_id=info, topic=topic,
                 source_id=s['knowledge'][actor][info], tick=s['tick'], order=_stamp(s))
    s['statements'].append(entry)
    if info == 'F':
        # A validated voluntary answer endorses the fact; merely receiving the
        # player's notice does not. The player still verifies via subject/professor.
        s['fact_holders'] = sorted(fact_holders(s) | {actor})
        if actor in s['unresolved']:
            s['unresolved'][actor] = []
    if info not in s['heard']:
        s['heard'].append(info)
    if info == 'S' and topic == 'SOURCE' and actor == s['roles']['origin']:
        entry['origin_found'] = True
    if info == 'F' and topic == 'VERIFY' and actor in (s['roles']['subject'], s['professor']):
        s['verified'], s['verified_at'] = ['F'], entry['order']
    return True


def compare_statements(s, indices):
    if len(indices) != 2 or any(i < 0 or i >= len(s['statements']) for i in indices):
        raise ValueError('비교할 학생 진술 두 개를 선택하세요.')
    entries = [s['statements'][i] for i in indices]
    if len({e['actor'] for e in entries}) != 2 or any(e['actor'] not in s['students'] for e in entries):
        raise ValueError('서로 다른 학생의 진술이 필요합니다.')
    s['compared_at'] = _stamp(s)
    s['history'].append(dict(kind='COMPARE', statements=indices, tick=s['tick'], order=s['compared_at']))


def fact_holders(s):
    # 이전 미커밋 구현으로 저장된 run도 기존 증언/정정 이력으로 이어갈 수 있다.
    holders = set(s.get('fact_holders', ()))
    holders.update((s['roles']['subject'], s['roles']['witness'], s['professor']))
    for entry in s['history']:
        if entry['kind'] in ('TESTIFY', 'CORRECT'):
            holders.update((entry['actor'], entry['target']))
    return holders


def misinformed_students(s):
    return {actor for actor in s['students'] if s['unresolved'][actor] and actor not in fact_holders(s)}


def school_spread_active(s):
    mistaken = misinformed_students(s)
    return (len(s['reached']) >= SCHOOL_SPREAD_THRESHOLD
            and len(mistaken) >= SCHOOL_MISUNDERSTANDING_THRESHOLD
            and any(h['kind'] == 'TRANSFER' and h['actor'] in mistaken for h in s['history']))


def _spread(s):
    if school_spread_active(s) and s['school_spread_tick'] is None:
        s['school_spread_tick'] = s['tick']


def submit_intervention(s, choice, target, info, elapsed):
    if not needs_intervention(s):
        raise ValueError('현재는 개입할 수 없습니다.')
    if choice not in CHOICES:
        raise ValueError('알 수 없는 개입입니다.')
    if choice in ('SHARE', 'REQUEST_TESTIMONY', 'REQUEST_CORRECTION'):
        if target not in s['students'] or info not in s['heard']:
            raise ValueError('대상 학생과 실제로 들은 정보를 선택하세요.')
        if choice == 'SHARE' and (info == 'S' or (info == 'F' and 'F' not in s['verified'])):
            raise ValueError('개인의 출처 진술은 기록으로 비교하세요. 사실 전달은 먼저 당사자 또는 교수에게 확인해야 합니다.')
    elif choice == 'PUBLISH_FACT':
        if 'F' not in s['verified']:
            raise ValueError('먼저 당사자 또는 교수에게 사실을 확인하세요.')
        target, info = 'all', 'F'
    else:
        target, info = None, None
    s['interventions'].append(dict(choice=choice, target=target, information_id=info, tick=s['tick'],
                                   elapsed_seconds=elapsed, order=_stamp(s)))
    if choice in ('SHARE', 'PUBLISH_FACT'):
        for actor in s['students'] if target == 'all' else [target]:
            s['knowledge'][actor][info] = 'player'
            if info.startswith('R'):
                if actor not in fact_holders(s) and info not in s['unresolved'][actor]:
                    s['unresolved'][actor].append(info)
                if actor not in s['reached']:
                    s['reached'].append(actor)
                s['flame_links'].append([actor, info, 'player'])
            s['history'].append(dict(kind='PLAYER_SHARE', actor='player', target=actor,
                                     information_id=info, source_id='player', tick=s['tick']))
        _spread(s)


def apply_acts(s, acts):
    """서비스에서 실제 실행을 검증한 acts의 정보 범위를 batch 시작 snapshot으로 검증."""
    snapshot = deepcopy(s['knowledge'])
    for act in acts:
        actor, target, info, source, kind = (act[k] for k in ('actor', 'target', 'information_id', 'source_id', 'kind'))
        if actor not in s['students'] or target not in s['knowledge'] or actor == target:
            continue
        known = snapshot[actor]
        valid = known.get(info) == source
        if kind == 'TRANSFER' and info.startswith('R'):
            valid = valid or any(NEXT_VARIANT.get(i) == info and src == source for i, src in known.items())
        elif kind in ('TESTIFY', 'CORRECT'):
            valid = valid and info == 'F'
            if kind == 'CORRECT':
                valid = valid and any(h['kind'] in ('INITIAL', 'TRANSFER') and h['actor'] == actor and h['target'] == target for h in s['history'])
        else:
            continue
        entry = {**act, 'tick': s['tick']}
        if not valid or info not in INFORMATION or entry in s['history']:
            continue
        novel_misinformation = info not in snapshot[target] and target not in fact_holders(s)
        s['history'].append(entry)
        s['knowledge'][target][info] = actor
        if kind == 'TRANSFER':
            s['knowledge'][actor][info] = source
            if target in s['students']:
                if target not in fact_holders(s) and info not in s['unresolved'][target]:
                    s['unresolved'][target].append(info)
                if target not in s['reached']:
                    s['reached'].append(target)
            if any(link[0] == actor and (link[1] == info or NEXT_VARIANT.get(link[1]) == info)
                   and link[2] == source for link in s['flame_links']):
                if novel_misinformation:
                    s['flame'] = True
                s['flame_links'].append([target, info, actor])
        else:
            s['fact_holders'] = sorted(fact_holders(s) | {actor, target})
            if actor in s['unresolved']:
                s['unresolved'][actor] = []
            if target in s['unresolved']:
                s['unresolved'][target] = []
            if kind == 'CORRECT':
                s['unresolved'][actor], s['corrected'] = [], True
            if kind == 'TESTIFY' and actor == s['roles']['witness'] and not any(
                h['kind'] == 'TESTIFY' and h['actor'] == actor for h in s['history'][:-1]) and any(
                x['choice'] == 'REQUEST_TESTIMONY' and x['target'] == actor and x['tick'] < s['tick']
                for x in s['interventions']):
                s['witness_spoke'] = True
        if info not in s['heard']:
            s['heard'].append(info)
    _spread(s)


def finish(s):
    unresolved = len(misinformed_students(s))
    if s['verified'] and unresolved == 0:
        s['ending'], s['grade'] = 'RESOLVED', 'GOOD'
    elif school_spread_active(s):
        s['ending'], s['grade'] = 'SPREAD', 'BAD'
    else:
        s['ending'], s['grade'] = 'MISUNDERSTANDING', 'MIXED'
    records = [InterventionRecord(str(x['tick']), x['choice'], x['elapsed_seconds']) for x in s['interventions']]
    comparisons = [e['order'] for e in s['history'] if e['kind'] == 'COMPARE' and 'order' in e]
    if not comparisons and s['compared_at'] is not None:
        comparisons = [s['compared_at']]
    verifications = [e['order'] for e in s['statements']
                     if e['information_id'] == 'F' and e['topic'] == 'VERIFY'
                     and e['actor'] in (s['roles']['subject'], s['professor'])]
    conditions = {
        'CHAPTER1_CLEAR': s['tick'] == TOTAL_TICKS,
        'FIRST_SENTENCE': any(e.get('origin_found') for e in s['statements']),
        'HEARD_AND_SEEN': any(compared < verified < e['order'] and e['choice'] != 'WATCH'
                              for compared in comparisons for verified in verifications
                              for e in s['interventions']),
        'FAN_THE_FLAME': s['flame'], 'SILENT_WITNESS': s['witness_spoke'],
        'THREE_RUMORS': all(i in s['heard'] for i in ('R0', 'R1', 'R2')),
        'AHEAD_OF_RUMOR': s['tick'] == TOTAL_TICKS and s['grade'] == 'GOOD' and s['school_spread_tick'] is None,
        'SELF_CORRECTION': s['corrected'], 'INDECISIVE': is_indecisive(records),
    }
    s['achievements'] = [key for key, earned in conditions.items() if earned]
    s['chapter_record'] = asdict(ChapterRecord(1, s['ending'], ChapterGrade(s['grade']), tuple(records)))


def needs_intervention(s):
    return s['tick'] in INTERVENTION_TICKS and not any(x['tick'] == s['tick'] for x in s['interventions'])


def public_state(s):
    round_no = min(ROUND_COUNT, max(0, s['tick'] - 1) // TICKS_PER_ROUND + 1)
    return dict(current_tick=s['tick'], current_round=round_no,
                status='completed' if s['tick'] == TOTAL_TICKS else 'in_progress',
                needs_intervention=needs_intervention(s),
                inquiries_remaining=max(0, INQUIRIES_PER_ROUND - s['inquiries'].get(str(round_no), 0)),
                statements=[{k: v for k, v in e.items() if k != 'origin_found'} | {'text': INFORMATION[e['information_id']]}
                            for e in s['statements']],
                information=[dict(id=i, text=INFORMATION[i], confirmed=i in s['verified']) for i in s['heard']],
                history=[{**e, 'text': INFORMATION[e['information_id']]}
                         for e in s['history'] if e['kind'] in ('TRANSFER', 'TESTIFY', 'CORRECT', 'PLAYER_SHARE')],
                interventions=s['interventions'], school_spread=s['school_spread_tick'] is not None,
                rumor_awareness_count=len(s['reached']), misinformed_count=len(misinformed_students(s)),
                school_spread_active=school_spread_active(s),
                ending=s['ending'], grade=s['grade'], chapter_record=s.get('chapter_record'),
                achievements=[dict(id=i, label=ACHIEVEMENTS[i]) for i in s['achievements']],
                choices=[dict(value=k, label=v) for k, v in CHOICES.items()],
                topics=[dict(value=k, label=v) for k, v in TOPICS.items()])
