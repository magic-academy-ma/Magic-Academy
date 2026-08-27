import { mockAgents } from "./agents.js";

const LOCATIONS = [
  { id: "01900000-0000-7000-8000-000000000021", code: "classroom",  name: "교실" },
  { id: "01900000-0000-7000-8000-000000000022", code: "dormitory",  name: "기숙사" },
  { id: "01900000-0000-7000-8000-000000000023", code: "restaurant", name: "식당" },
  { id: "01900000-0000-7000-8000-000000000024", code: "library",    name: "도서관" },
  { id: "01900000-0000-7000-8000-000000000025", code: "lab",        name: "연구실" },
];

function buildWorldMap(agents) {
  const byLocationId = new Map(LOCATIONS.map((loc) => [loc.id, { ...loc, agents: [] }]));

  for (const agent of agents) {
    const locId = agent.location?.id;
    if (locId && byLocationId.has(locId)) {
      byLocationId.get(locId).agents.push(agent);
    }
  }

  return { locations: [...byLocationId.values()] };
}

export const mockWorldMap = buildWorldMap(mockAgents);
