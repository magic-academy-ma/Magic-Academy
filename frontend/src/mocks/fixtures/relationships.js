const PROF = "01900000-0000-7000-8000-000000000011";
const ADEL = "01900000-0000-7000-8000-000000000012";
const LEO  = "01900000-0000-7000-8000-000000000013";
const RIA  = "01900000-0000-7000-8000-000000000014";
const KAI  = "01900000-0000-7000-8000-000000000015";
const SERA = "01900000-0000-7000-8000-000000000016";

function rel(id, name, { affection, closeness, trust, tension, rivalry, dep, type }) {
  return {
    target_agent_id: id,
    target_agent_name: name,
    affection,
    closeness,
    trust,
    tension,
    rivalry,
    dependency: dep,
    relationship_type: type,
  };
}

export const mockRelationships = {
  [PROF]: [
    rel(ADEL, "아델", { affection: 30, closeness: 40, trust: 65, tension: 10, rivalry: 0, dep: 15, type: "신뢰" }),
    rel(LEO,  "레오", { affection: 20, closeness: 25, trust: 25, tension: 45, rivalry: 0, dep: 5,  type: "우려" }),
    rel(RIA,  "리아", { affection: 35, closeness: 35, trust: 55, tension: 5,  rivalry: 0, dep: 10, type: "신뢰" }),
    rel(KAI,  "카이", { affection: 25, closeness: 30, trust: 45, tension: 20, rivalry: 0, dep: 5,  type: "중립" }),
    rel(SERA, "세라", { affection: 35, closeness: 40, trust: 60, tension: 5,  rivalry: 0, dep: 8,  type: "신뢰" }),
  ],
  [ADEL]: [
    rel(LEO,  "레오", { affection: -8, closeness: 30, trust: 25, tension: 72, rivalry: 20, dep: 10, type: "긴장" }),
    rel(RIA,  "리아", { affection: 72, closeness: 68, trust: 85, tension: 12, rivalry: 0,  dep: 20, type: "우호" }),
    rel(KAI,  "카이", { affection: 15, closeness: 31, trust: 31, tension: 35, rivalry: 25, dep: 15, type: "중립" }),
    rel(SERA, "세라", { affection: 55, closeness: 44, trust: 44, tension: 20, rivalry: 0,  dep: 18, type: "우호" }),
    rel(PROF, "에단", { affection: 25, closeness: 35, trust: 70, tension: 8,  rivalry: 0,  dep: 20, type: "신뢰" }),
  ],
  [LEO]: [
    rel(ADEL, "아델", { affection: 10, closeness: 25, trust: 20, tension: 40, rivalry: 15, dep: 5,  type: "긴장" }),
    rel(RIA,  "리아", { affection: 80, closeness: 75, trust: 78, tension: 15, rivalry: 0,  dep: 25, type: "친구" }),
    rel(KAI,  "카이", { affection: 60, closeness: 55, trust: 65, tension: 22, rivalry: 30, dep: 10, type: "우호" }),
    rel(SERA, "세라", { affection: 30, closeness: 30, trust: 35, tension: 25, rivalry: 0,  dep: 8,  type: "중립" }),
    rel(PROF, "에단", { affection: 15, closeness: 25, trust: 20, tension: 55, rivalry: 0,  dep: 10, type: "긴장" }),
  ],
  [RIA]: [
    rel(ADEL, "아델", { affection: 70, closeness: 65, trust: 82, tension: 10, rivalry: 0,  dep: 22, type: "우호" }),
    rel(LEO,  "레오", { affection: 75, closeness: 70, trust: 72, tension: 18, rivalry: 0,  dep: 28, type: "친구" }),
    rel(KAI,  "카이", { affection: 25, closeness: 30, trust: 40, tension: 30, rivalry: 0,  dep: 12, type: "중립" }),
    rel(SERA, "세라", { affection: 45, closeness: 45, trust: 48, tension: 18, rivalry: 0,  dep: 75, type: "의존" }),
    rel(PROF, "에단", { affection: 40, closeness: 35, trust: 60, tension: 5,  rivalry: 0,  dep: 15, type: "신뢰" }),
  ],
  [KAI]: [
    rel(ADEL, "아델", { affection: 15, closeness: 30, trust: 30, tension: 35, rivalry: 30, dep: 62, type: "의존" }),
    rel(LEO,  "레오", { affection: 55, closeness: 50, trust: 60, tension: 25, rivalry: 20, dep: 12, type: "우호" }),
    rel(RIA,  "리아", { affection: 25, closeness: 28, trust: 38, tension: 28, rivalry: 0,  dep: 10, type: "중립" }),
    rel(SERA, "세라", { affection: 30, closeness: 40, trust: 48, tension: 45, rivalry: 10, dep: 8,  type: "긴장" }),
    rel(PROF, "에단", { affection: 20, closeness: 30, trust: 45, tension: 30, rivalry: 0,  dep: 15, type: "중립" }),
  ],
  [SERA]: [
    rel(ADEL, "아델", { affection: 58, closeness: 50, trust: 48, tension: 20, rivalry: 0,  dep: 15, type: "우호" }),
    rel(LEO,  "레오", { affection: 35, closeness: 32, trust: 30, tension: 28, rivalry: 0,  dep: 10, type: "중립" }),
    rel(RIA,  "리아", { affection: 72, closeness: 68, trust: 65, tension: 18, rivalry: 0,  dep: 70, type: "의존·우호" }),
    rel(KAI,  "카이", { affection: 28, closeness: 38, trust: 48, tension: 45, rivalry: 8,  dep: 5,  type: "긴장" }),
    rel(PROF, "에단", { affection: 38, closeness: 42, trust: 65, tension: 5,  rivalry: 0,  dep: 12, type: "신뢰" }),
  ],
};
