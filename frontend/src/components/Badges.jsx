export function StatusBadge({ match }) {
  return (
    <span className={match ? "badge badgeMatch" : "badge badgeMismatch"}>
      {match ? "Match" : "Flag"}
    </span>
  );
}

export function MailStatusBadge({ status }) {
  const statusMap = {
    pending: ["workflowBadge workflowPending", "PENDING"],
    completed: ["workflowBadge workflowCompleted", "COMPLETED"],
  };
  const [className, label] = statusMap[status] || [
    "workflowBadge workflowNew",
    "NEW",
  ];

  return <span className={className}>{label}</span>;
}

export function VerificationStatusBadge({ status }) {
  const statusMap = {
    PROCESSING: ["workflowBadge workflowPending", "Processing"],
    VERIFIED: ["badge badgeMatch", "Verified"],
    NEEDS_HUMAN_REVIEW: ["badge badgeMismatch", "Needs Review"],
    PENDING_DOCUMENTS: ["workflowBadge workflowPending", "Pending Documents"],
    SYSTEM_ERROR: ["badge badgeMismatch", "System Error"],
  };
  const [className, label] = statusMap[status] || ["workflowBadge workflowNew", status || "Unknown"];

  return <span className={className}>{label}</span>;
}
