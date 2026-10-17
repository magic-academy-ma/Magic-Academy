from copy import deepcopy

import pytest

from app.simulation.challenge.rumor import (
    initialize, submit_intervention, apply_acts, investigate_answer,
    finish, public_state, agent_context, compare_statements,
)


def make(seed=7):
    return initialize([f's{i}' for i in range(5)], 'prof', seed)


def test_seed_and_private_information():
    state = make()
    assert state == make()
    assert state['roles'] != make(8)['roles']
    text = str(public_state(state))
    assert 'roles' not in text and 'truth' not in text and 'motive' not in text
    origin = state['roles']['origin']
    assert 'F' not in agent_context(state, origin)['information']
    assert 'motive' not in agent_context(state, origin)
    assert 'F' in agent_context(state, state['roles']['witness'])['information']


def test_requests_do_not_force_actions_and_truth_is_fixed():
    s = make()
    s['tick'] = 1
    witness = s['roles']['witness']
    investigate_answer(s, s['roles']['origin'], 'RUMOR', 'R0')
    before = deepcopy(s['truth'])
    submit_intervention(s, 'REQUEST_TESTIMONY', witness, 'R0', 301)
    assert not any(x['kind'] == 'TESTIFY' for x in s['history'])
    assert s['truth'] == before
    finish(s)
    assert 'INDECISIVE' in s['achievements']


def test_validated_transfer_correction_and_snapshot_scope():
    s = make()
    a, b, c = (s['roles'][k] for k in ('origin', 'believer', 'subject'))
    acts = [dict(actor=a, target=b, information_id='R1', source_id=a, kind='TRANSFER'),
            dict(actor=b, target=c, information_id='R1', source_id=a, kind='TRANSFER')]
    apply_acts(s, acts)
    assert 'R1' in s['unresolved'][b]
    assert 'R1' not in s['knowledge'][c]  # cannot use same-batch new knowledge
    apply_acts(s, [dict(actor=a, target=b, information_id='F', source_id=a, kind='CORRECT')])
    assert s['unresolved'][b]  # unknown F rejected
    apply_acts(s, [dict(actor=c, target=a, information_id='F', source_id=c, kind='TESTIFY')])
    apply_acts(s, [dict(actor=a, target=b, information_id='F', source_id=c, kind='CORRECT')])
    assert not s['unresolved'][b]
    finish(s)
    assert 'SELF_CORRECTION' in s['achievements']


def test_inquiry_scope_source_comparison_and_three_variants():
    s = make()
    origin, exaggerator, believer = (s['roles'][k] for k in ('origin', 'exaggerator', 'believer'))
    assert not investigate_answer(s, believer, 'VERIFY', 'F')
    for actor, info in ((origin, 'R0'), (exaggerator, 'R1'), (believer, 'R2')):
        assert investigate_answer(s, actor, 'RUMOR', info)
    assert investigate_answer(s, origin, 'SOURCE', 'S')
    compare_statements(s, [0, 1])
    assert investigate_answer(s, 'prof', 'VERIFY', 'F')
    s['tick'] = 1
    submit_intervention(s, 'PUBLISH_FACT', None, 'F', 1)
    finish(s)
    assert {'FIRST_SENTENCE', 'THREE_RUMORS', 'HEARD_AND_SEEN'} <= set(s['achievements'])
    with pytest.raises(ValueError):
        compare_statements(s, [0, 0])


def test_flame_witness_and_ending_paths():
    s = make()
    origin, witness, believer = (s['roles'][k] for k in ('origin', 'witness', 'believer'))
    investigate_answer(s, origin, 'RUMOR', 'R0')
    s['tick'] = 1
    submit_intervention(s, 'SHARE', believer, 'R0', 1)
    s['tick'] = 2
    apply_acts(s, [dict(actor=believer, target=origin, information_id='R1', source_id='player', kind='TRANSFER')])
    s['tick'] = 4
    submit_intervention(s, 'REQUEST_TESTIMONY', witness, 'R0', 1)
    s['tick'] = 5
    apply_acts(s, [dict(actor=witness, target=origin, information_id='F', source_id=witness, kind='TESTIFY')])
    finish(s)
    assert {'FAN_THE_FLAME', 'SILENT_WITNESS'} <= set(s['achievements'])
    assert s['grade'] == 'MIXED'

    bad = make()
    origin = bad['roles']['origin']
    for role in ('subject', 'witness'):
        apply_acts(bad, [dict(actor=origin, target=bad['roles'][role], information_id='R0', source_id=origin, kind='TRANSFER')])
    finish(bad)
    assert bad['school_spread_tick'] is not None and bad['grade'] == 'BAD'
    witness = bad['roles']['witness']
    for role in ('origin', 'exaggerator', 'believer'):
        apply_acts(bad, [dict(actor=witness, target=bad['roles'][role], information_id='F', source_id=witness, kind='TESTIFY')])
    investigate_answer(bad, 'prof', 'VERIFY', 'F')
    bad['tick'] = 9
    finish(bad)
    assert bad['grade'] == 'GOOD' and 'CHAPTER1_CLEAR' in bad['achievements']
    assert 'AHEAD_OF_RUMOR' not in bad['achievements']


def test_early_resolution_path():
    s = make()
    investigate_answer(s, 'prof', 'VERIFY', 'F')
    witness = s['roles']['witness']
    for target in s['students']:
        if target != witness:
            apply_acts(s, [dict(actor=witness, target=target, information_id='F', source_id=witness, kind='TESTIFY')])
    s['tick'] = 9
    finish(s)
    assert s['grade'] == 'GOOD'
    assert 'AHEAD_OF_RUMOR' in s['achievements']


@pytest.mark.parametrize('change', [dict(source_id='forged'), dict(target='unknown'), dict(information_id='F')])
def test_forged_act_does_not_change_information(change):
    s = make()
    a, b = [s['roles'][k] for k in ('origin', 'subject')]
    old = deepcopy(s)
    act = dict(actor=a, target=b, information_id='R0', source_id=a, kind='TRANSFER') | change
    apply_acts(s, [act])
    assert s == old


def test_a_witness_who_already_spoke_cannot_break_silence_again():
    s = make()
    witness, origin = [s['roles'][k] for k in ('witness', 'origin')]
    apply_acts(s, [dict(actor=witness, target=origin, information_id='F', source_id=witness, kind='TESTIFY')])
    s['tick'] = 1
    submit_intervention(s, 'REQUEST_TESTIMONY', witness, 'F', 1)
    s['tick'] = 2
    apply_acts(s, [dict(actor=witness, target=s['roles']['believer'], information_id='F', source_id=witness, kind='TESTIFY')])
    finish(s)
    assert 'SILENT_WITNESS' not in s['achievements']


@pytest.mark.parametrize('info', ['S', 'F'])
def test_personal_source_claim_or_unverified_fact_cannot_be_shared_as_evidence(info):
    s = make()
    actor = s['roles']['origin'] if info == 'S' else s['roles']['witness']
    topic = 'SOURCE' if info == 'S' else 'OBSERVED'
    investigate_answer(s, actor, topic, info)
    s['tick'] = 1
    with pytest.raises(ValueError):
        submit_intervention(s, 'SHARE', s['roles']['believer'], info, 1)


def test_hearing_rumor_does_not_make_firsthand_witnesses_believe_it():
    s = make()
    origin = s['roles']['origin']
    for role in ('subject', 'witness'):
        target = s['roles'][role]
        apply_acts(s, [dict(actor=origin, target=target, information_id='R0', source_id=origin, kind='TRANSFER')])
        assert target in s['reached']
        assert not s['unresolved'][target]
        assert agent_context(s, target)['information']['R0']['confirmed'] is False
    assert origin in s['reached']  # original producer is part of awareness, not a new recipient
    assert public_state(s)['rumor_awareness_count'] == 5
    assert public_state(s)['misinformed_count'] == 3


def test_schoolwide_history_does_not_block_resolution_after_actual_testimony():
    s = make()
    origin, witness = [s['roles'][r] for r in ('origin', 'witness')]
    for role in ('subject', 'witness'):
        apply_acts(s, [dict(actor=origin, target=s['roles'][role], information_id='R0', source_id=origin, kind='TRANSFER')])
    assert s['school_spread_tick'] is not None
    for role in ('origin', 'exaggerator', 'believer'):
        apply_acts(s, [dict(actor=witness, target=s['roles'][role], information_id='F', source_id=witness, kind='TESTIFY')])
    investigate_answer(s, 'prof', 'VERIFY', 'F')
    s['tick'] = 9
    finish(s)
    assert s['grade'] == 'GOOD'
    assert public_state(s)['school_spread_active'] is False
    assert 'AHEAD_OF_RUMOR' not in s['achievements']


def test_player_notice_is_evidence_not_automatic_belief_or_correction():
    s = make()
    investigate_answer(s, 'prof', 'VERIFY', 'F')
    s['tick'] = 1
    before = deepcopy(s['unresolved'])
    submit_intervention(s, 'PUBLISH_FACT', None, 'F', 1)
    assert s['unresolved'] == before
    origin = s['roles']['origin']
    assert agent_context(s, origin)['information']['F']['accepted'] is False
    assert not any(h['kind'] in ('TESTIFY', 'CORRECT') for h in s['history'])


def test_receipt_history_alone_never_counts_as_schoolwide_spread():
    s = make()
    s['reached'] = list(s['students'])
    s['tick'] = 9
    finish(s)
    assert s['grade'] == 'MIXED'
    assert public_state(s)['school_spread_active'] is False


def test_voluntary_fact_answer_updates_student_belief_but_not_player_verification():
    s = make()
    investigate_answer(s, 'prof', 'VERIFY', 'F')
    s['tick'] = 1
    submit_intervention(s, 'PUBLISH_FACT', None, 'F', 1)
    origin = s['roles']['origin']
    assert s['unresolved'][origin]
    assert investigate_answer(s, origin, 'OBSERVED', 'F')
    assert not s['unresolved'][origin]
    assert agent_context(s, origin)['fact_accepted']
    for actor in s['students']:
        assert all(h['actor'] == actor for h in agent_context(s, actor)['my_transmissions'])
