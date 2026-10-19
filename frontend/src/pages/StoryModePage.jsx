import { useCallback, useEffect, useState } from "react";

import { apiRequest } from "../api/client.js";
import ClubChallengePage from "./ClubChallengePage.jsx";
import RumorChapterPage from "./RumorChapterPage.jsx";
import StoryChapterPlay from "./StoryChapterPlay.jsx";
import { CHAPTERS, FINAL_ENDINGS, FINAL_INTRO, GRADE_LABELS, PROLOGUE } from "./storyScript.js";
import "./StoryModePage.css";

const ROOT = "/v1/story";
const FINAL_STAGE = 5;

function RecordList({ records }) {
  if (records.length === 0) return null;
  return <ol className="story-records" aria-label="활동 기록">
    {records.map((record) => {
      const chapter = CHAPTERS[record.chapter];
      return <li key={record.chapter}>
        <b>CHAPTER {record.chapter} · {chapter.recordTitle}</b>
        <span className={`story-grade story-grade--${record.grade.toLowerCase()}`}>{GRADE_LABELS[record.grade]}</span>
        <p>{chapter.endings[record.ending] ?? record.ending}</p>
      </li>;
    })}
  </ol>;
}

// 방금 끝낸 챕터에서 처음 달성한 업적 — 챕터 완료 응답에만 담긴다.
function NewAchievements({ achievements = [] }) {
  if (achievements.length === 0) return null;
  return <section className="story-achievements" aria-label="새 업적">
    <p className="story-eyebrow">업적 달성</p>
    <ul>{achievements.map((achievement) => <li key={achievement.id}>{achievement.name}</li>)}</ul>
  </section>;
}

export default function StoryModePage({ auth, onBack }) {
  const token = auth.access_token;
  const [story, setStory] = useState(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const call = useCallback(async (path, method = "GET") => {
    setLoading(true);
    setError("");
    try {
      const response = await apiRequest(path, { token, method });
      setStory(response.data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { call(`${ROOT}/current`); }, [call]);

  const startStory = () => call(ROOT, "POST");
  const takeChapter = () => call(`${ROOT}/${story.id}/chapter/start`, "POST");
  const completeChapter = () => call(`${ROOT}/${story.id}/chapter/complete`, "POST");

  if (story === undefined) {
    return <main className="story-page"><p role="status">{error || "활동 기록을 불러오는 중..."}</p></main>;
  }

  // 프롤로그 — 아직 이번 학기를 시작하지 않았다.
  if (story === null) {
    return <main className="story-page">
      <button type="button" className="story-back" onClick={onBack}>← 메인으로</button>
      <section className="story-card">
        <p className="story-eyebrow">PROLOGUE</p>
        <h1>{PROLOGUE.title}</h1>
        {PROLOGUE.paragraphs.map((text) => <p key={text}>{text}</p>)}
        <blockquote>{PROLOGUE.quote}</blockquote>
        <p>{PROLOGUE.closing}</p>
        {error && <p role="alert">{error}</p>}
        <button type="button" className="story-primary" disabled={loading} onClick={startStory}>임시 조정관 임명을 받아들인다</button>
      </section>
    </main>;
  }

  // FINAL — 「한 학기의 기록」
  if (story.chapter === FINAL_STAGE) {
    const ending = FINAL_ENDINGS[story.final_ending];
    return <main className="story-page">
      <button type="button" className="story-back" onClick={onBack}>← 메인으로</button>
      <section className="story-card">
        <NewAchievements achievements={story.new_achievements} />
        <p className="story-eyebrow">FINAL</p>
        <h1>한 학기의 기록</h1>
        {FINAL_INTRO.map((text) => <p key={text}>{text}</p>)}
        <RecordList records={story.records} />
        <div className={`story-ending story-ending--${story.final_ending.toLowerCase()}`}>
          <p className="story-eyebrow">{ending.label}</p>
          <h2>「{ending.title}」</h2>
          {ending.paragraphs.map((text) => <p key={text}>{text}</p>)}
          <p className="story-caption">{ending.caption}</p>
        </div>
        {error && <p role="alert">{error}</p>}
        <button type="button" className="story-primary" disabled={loading} onClick={startStory}>새 학기 시작</button>
      </section>
    </main>;
  }

  const chapter = CHAPTERS[story.chapter];

  // 사건 도입 — 아직 이 사건을 맡지 않았다.
  if (!story.chapter_run_id) {
    return <main className="story-page">
      <button type="button" className="story-back" onClick={onBack}>← 메인으로</button>
      <section className="story-card">
        <NewAchievements achievements={story.new_achievements} />
        <RecordList records={story.records} />
        <p className="story-eyebrow">CHAPTER {story.chapter} · {chapter.theme}</p>
        <h1>{chapter.title}</h1>
        {chapter.paragraphs.map((text) => <p key={text}>{text}</p>)}
        {error && <p role="alert">{error}</p>}
        <button type="button" className="story-primary" disabled={loading} onClick={takeChapter}>{loading ? "사건 준비 중..." : "사건을 맡는다"}</button>
      </section>
    </main>;
  }

  const playProps = { runId: story.chapter_run_id, onBack, onComplete: completeChapter };
  return <>
    {story.chapter === 1 && <RumorChapterPage auth={auth} {...playProps} />}
    {story.chapter === 3 && <ClubChallengePage token={token} {...playProps} />}
    {[2, 4].includes(story.chapter) && <StoryChapterPlay key={story.chapter_run_id} chapter={story.chapter} token={token} {...playProps} />}
    {error && <p className="story-toast" role="alert">{error}</p>}
  </>;
}
