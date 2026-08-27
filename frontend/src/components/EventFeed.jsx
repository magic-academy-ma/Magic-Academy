// STUDENT_MISSING 등 세부 종류 구분 필드가 명세에 없어 RANDOM_INCIDENT만 강조 표시
export default function EventFeed({ events }) {
  if (events.length === 0) return null;

  return (
    <ul className="event-feed">
      {events.map((e) => (
        <li
          key={e.event_id}
          className={e.event_type === "RANDOM_INCIDENT" ? "event-item event-item-special" : "event-item"}
        >
          <span className="event-type">{e.event_type}</span>
          <span className="event-title">{e.title}</span>
          {e.location && <span className="event-location">@ {e.location}</span>}
        </li>
      ))}
    </ul>
  );
}
