import { useEffect, useState } from 'react';
import { apiRequest } from '../api/client.js';

const KIND_LABELS = { PROGRESS: '진행', OBSERVATION: '관찰', INTERVENTION: '개입', OUTCOME: '결과' };

function formatAchievedAt(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('ko-KR');
}

function groupByGroup(achievements) {
  const groups = [];
  for (const achievement of achievements) {
    const last = groups[groups.length - 1];
    if (last?.name === achievement.group) last.items.push(achievement);
    else groups.push({ name: achievement.group, items: [achievement] });
  }
  return groups;
}

export default function MyAchievements({ auth }) {
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiRequest('/v1/achievements', { token: auth.access_token })
      .then((result) => { if (active) setAchievements(result.data); })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [auth.access_token]);

  const achievedCount = achievements.filter((item) => item.achieved).length;

  return (
    <>
      <header className="page-header">
        <div>
          <div className="page-eyebrow">Achievements</div>
          <h1 className="page-title">업적</h1>
          <p className="page-description">
            {loading || error ? '스토리모드와 자유 모드에서 달성한 업적을 확인할 수 있습니다.' : `${achievements.length}개 중 ${achievedCount}개 달성`}
          </p>
        </div>
      </header>

      {loading && <p className="mypage-message">업적을 불러오는 중...</p>}
      {error && <p className="mypage-message mypage-message--error" role="alert">{error}</p>}
      {!loading && !error && groupByGroup(achievements).map((group) => (
        <section key={group.name} className="achievement-group" aria-label={group.name}>
          <h2 className="achievement-group__title">{group.name}</h2>
          <ul className="achievement-list">
            {group.items.map((item) => (
              <li key={item.id} className={`achievement-card${item.achieved ? ' achieved' : ''}`}>
                <div className="achievement-card__head">
                  <span className="achievement-card__name">{item.name}</span>
                  <span className="achievement-card__kind">{KIND_LABELS[item.kind] ?? item.kind}</span>
                </div>
                <p className="achievement-card__condition">{item.condition}</p>
                <span className="achievement-card__state">
                  {item.achieved ? `달성 · ${formatAchievedAt(item.achieved_at)}` : '미달성'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
