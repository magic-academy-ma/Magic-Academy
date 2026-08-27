function formatDelta(delta) {
  return delta > 0 ? `+${delta}` : `${delta}`;
}

export default function RelationshipChangesPanel({ updates = [] }) {
  if (updates.length === 0) return null;

  return (
    <table className="relationship-changes">
      <thead>
        <tr>
          <th>관계</th>
          <th>변화</th>
        </tr>
      </thead>
      <tbody>
        {updates.map((u) => (
          <tr key={u.relationship_id}>
            <td>
              Agent {u.source_agent_id} → {u.target_agent_id}
            </td>
            <td>
              {Object.entries(u.changes).map(([metric, delta]) => (
                <span key={metric} className="delta-chip">
                  {metric} {formatDelta(delta)}
                </span>
              ))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
