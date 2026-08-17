/**
 * 도메인 규칙(docs/02-domain/)을 준수하는 학생 Agent Mock 데이터
 */
export const mockAgents = [
  {
    id: "agent-001",
    name: "카엘 윈드스톰",
    gender: "MALE",
    role: "STUDENT",
    element: "WIND",
    mbti: "ENTP",
    personality: "호기심 많고 도전적이며 규칙을 깨뜨리는 것을 즐김",
    state: {
      hunger: 25,
      fatigue: 40,
      stress: 15,
      mana: 85,
      current_action: "바람 마법 도서관에서 고대 주문 연구 중",
      location: "도서관 2층",
      affinity_with_player: 75,
    },
  },
  {
    id: "agent-002",
    name: "루나 실버하트",
    gender: "FEMALE",
    role: "STUDENT",
    element: "ICE",
    mbti: "INTJ",
    personality: "차분하고 분석적이며 감정을 쉽게 드러내지 않음",
    state: {
      hunger: 60,
      fatigue: 70,
      stress: 55,
      mana: 92,
      current_action: "빙결 마법 실습실에서 개인 수련",
      location: "제3실습실",
      affinity_with_player: 45,
    },
  },
  {
    id: "agent-003",
    name: "이그니스 플레임",
    gender: "MALE",
    role: "STUDENT",
    element: "FIRE",
    mbti: "ESTP",
    personality: "열정적이고 즉흥적이며 결투를 좋아함",
    state: {
      hunger: 80,
      fatigue: 20,
      stress: 10,
      mana: 60,
      current_action: "연무장에서 불꽃 격투 훈련",
      location: "대연무장",
      affinity_with_player: 90,
    },
  },
];
