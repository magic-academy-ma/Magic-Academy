"""Dialogue grouping — one mutual TALK pair per tick becomes one dialogue.

Pure unit tests (no DB). Grouping follows
``intent_conflict.resolve_talk_conflicts`` — see build_dialogue_drafts.
"""

from uuid import UUID

from app.services.dialogue_results import (
    InMemoryDialogueSink,
    build_dialogue_drafts,
)
from app.simulation.agent_runtime import AgentRuntimeResult
from app.simulation.intent_conflict import resolve_talk_conflicts

A = UUID("00000000-0000-0000-0000-00000000000a")
B = UUID("00000000-0000-0000-0000-00000000000b")
C = UUID("00000000-0000-0000-0000-00000000000c")
D = UUID("00000000-0000-0000-0000-00000000000d")


def talk(agent_id: UUID, target_id: UUID, utterance: str | None) -> AgentRuntimeResult:
    return AgentRuntimeResult.model_validate(
        {
            "run_id": "dlg-run",
            "tick_number": 7,
            "agent_id": agent_id,
            "status": "PROPOSED",
            "intent": {
                "action_type": "TALK",
                "target_agent_id": target_id,
                "target_location_id": None,
                "related_event_id": None,
                "utterance": utterance,
                "motivation_summary": "대화 요청",
                "reaction": {
                    "valence": "NEUTRAL",
                    "relationship_signals": [],
                    "state_signals": [],
                },
                "decision_explanation": {
                    "alternatives": [
                        {
                            "action_type": "TALK",
                            "description": "대화한다.",
                            "relative_priority": "HIGH",
                            "selected": True,
                        }
                    ],
                    "influencing_factors": [],
                },
                "memory_candidates": [],
            },
            "retry_count": 0,
            "failure_reason": None,
            "model": "test",
            "prompt_version": "test",
            "idempotency_key": f"dlg-run:7:{agent_id}",
        }
    )


def test_mutual_pair_becomes_one_dialogue_with_ordered_messages() -> None:
    resolution = resolve_talk_conflicts(
        (talk(A, B, "룬 결계가 불안정해."), talk(B, A, "나도 그렇게 느꼈어."))
    )

    drafts = build_dialogue_drafts(resolution)

    assert len(drafts) == 1
    draft = drafts[0]
    assert (draft.participant_a_id, draft.participant_b_id) == (A, B)
    assert draft.run_id == "dlg-run"
    assert draft.tick_number == 7
    assert [(m.order, m.speaker_agent_id, m.utterance) for m in draft.messages] == [
        (0, A, "룬 결계가 불안정해."),
        (1, B, "나도 그렇게 느꼈어."),
    ]


def test_unmatched_talk_produces_no_dialogue() -> None:
    # C 는 상대가 자신을 향해 TALK 하지 않아 WAIT_FALLBACK 이 된다.
    resolution = resolve_talk_conflicts(
        (talk(A, B, "안녕"), talk(B, A, "안녕"), talk(C, A, "나도 낄래"))
    )

    drafts = build_dialogue_drafts(resolution)

    assert len(drafts) == 1
    assert {draft.participant_a_id for draft in drafts} == {A}
    speakers = {m.speaker_agent_id for draft in drafts for m in draft.messages}
    assert C not in speakers


def test_two_independent_mutual_pairs_become_two_dialogues() -> None:
    resolution = resolve_talk_conflicts(
        (
            talk(A, B, "1"),
            talk(B, A, "2"),
            talk(C, D, "3"),
            talk(D, C, "4"),
        )
    )

    drafts = build_dialogue_drafts(resolution)

    assert {(d.participant_a_id, d.participant_b_id) for d in drafts} == {(A, B), (C, D)}


def test_missing_utterance_is_preserved_as_none() -> None:
    resolution = resolve_talk_conflicts((talk(A, B, None), talk(B, A, "말했어")))

    draft = build_dialogue_drafts(resolution)[0]

    assert [m.utterance for m in draft.messages] == [None, "말했어"]


def test_in_memory_sink_is_idempotent_on_pair_per_tick() -> None:
    resolution = resolve_talk_conflicts((talk(A, B, "x"), talk(B, A, "y")))
    sink = InMemoryDialogueSink()

    first = sink.save_batch(resolution)
    second = sink.save_batch(resolution)

    assert (first.new_count, first.duplicate_count) == (1, 0)
    assert (second.new_count, second.duplicate_count) == (0, 1)
    assert len(sink.list_drafts()) == 1
