export function StatusBadge({ match }) {
  return (
    <span className={match ? "badge badgeMatch" : "badge badgeMismatch"}>
      {match ? "Match" : "Flag"}
    </span>
  );
}

export function ProcessingStatusBadge({ status }) {
  const statusMap = {
    pending: ["processingBadge processingPending", "PENDING"],
    completed: ["processingBadge processingCompleted", "COMPLETED"],
  };
  const [className, label] = statusMap[status] || [
    "processingBadge processingNew",
    "NEW",
  ];

  return <span className={className}>{label}</span>;
}
