from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import User
from app.repositories.simulations import (
    list_agents_with_state,
    list_simulation_locations,
)
from app.services.simulations import require_owned_simulation


def get_world_map(db: Session, simulation_id: UUID, owner: User) -> dict:
    """학교 공간 목록과 각 공간에 위치한 Agent 를 조회한다 (API 명세 §10.1).

    새 저장소를 만들지 않고 이미 영속화된 두 소스만 합친다.

    * ``locations`` — 시뮬레이션 시드가 만든 공간 6종. ``id`` 는 프론트가 배경을
      매핑하는 ``Location.code`` 를, ``name`` 은 ``Location.name`` 을 사용한다.
    * 각 공간의 ``agents`` — ``AgentState.location_id`` 로 묶은 ``Agent.id`` (UUID
      문자열) 목록. F5-09 상세 조회(``GET /agents/{agent_id}``)와 WebSocket
      ``AGENT_ACTION_UPDATED`` 가 모두 UUID 를 쓰므로 형제 API 계약과 맞춘다.
      Agent 가 한 명도 없는 공간도 빈 배열로 포함한다.

    정렬은 기존 도메인 규칙을 재사용한다: 공간은 ``code`` 오름차순
    (``list_simulation_locations``), 공간 안의 Agent 는 ``fixture_key`` 오름차순
    (``list_agents_with_state``).
    """
    require_owned_simulation(db, simulation_id, owner)

    agents_by_location: dict[UUID, list[str]] = {}
    for agent, state, _location, _student, _professor in list_agents_with_state(
        db, simulation_id
    ):
        agents_by_location.setdefault(state.location_id, []).append(str(agent.id))

    return {
        "locations": [
            {
                "id": location.code,
                "name": location.name,
                "agents": agents_by_location.get(location.id, []),
            }
            for location in list_simulation_locations(db, simulation_id)
        ]
    }
