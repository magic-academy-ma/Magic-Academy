// Agent 한글 이름 → 캐릭터 이미지/Persona 키 매핑.
// 이미지 파일명은 영문이라 `${agent.name}_${mbti}.png` 같은 조합으로는 찾을 수 없다.
const CHARACTERS = {
  에단: { key: "ethan", portrait: "/assets/character/professor_orion.png" },
  아델: { key: "adel", portrait: "/assets/character/Adel_ISTJ.png" },
  레오: { key: "leo", portrait: "/assets/character/Leo_ESTP.png" },
  리아: { key: "ria", portrait: "/assets/character/Ria_INFP.png" },
  카이: { key: "kai", portrait: "/assets/character/Kai_ENTJ.png" },
  세라: { key: "sera", portrait: "/assets/character/Sera_ESFJ.png" },
};

export function portraitFor(name) {
  return CHARACTERS[name]?.portrait ?? null;
}

// PersonaSelectPage의 id(예: "adel")로 해당 학생 Agent를 찾는다.
export function findAgentByPersonaKey(agents, personaKey) {
  return agents.find((agent) => CHARACTERS[agent.name]?.key === personaKey) ?? null;
}
