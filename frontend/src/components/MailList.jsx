import { useState, useEffect } from "react";
import { Inbox, ChevronLeft, ChevronRight } from "lucide-react";
import { MailStatusBadge } from "./Badges";
import { formatDateTime } from "../utils/date";

export default function MailList({ emails, selectedId, onSelect }) {
  const [page, setPage] = useState(1);
  const itemsPerPage = 5;

  useEffect(() => {
    setPage(1);
  }, [emails]);

  const totalPages = Math.ceil(emails.length / itemsPerPage) || 1;
  const startIndex = (page - 1) * itemsPerPage;
  const endIndex = Math.min(startIndex + itemsPerPage, emails.length);
  const paginatedEmails = emails.slice(startIndex, startIndex + itemsPerPage);

  return (
    <section className="panel inboxPanel">
      <div className="panelHeader">
        <Inbox size={18} />
        <h2>Mails</h2>
      </div>
      <div className="emailList">
        {paginatedEmails.map((email) => (
          <button
            className={email.id === selectedId ? "emailRow selected" : "emailRow"}
            key={email.id}
            onClick={() => onSelect(email.id)}
            type="button"
          >
            <span className="emailSubject">{email.subject}</span>
            <span className="emailSender">{email.sender}</span>
            <div className="emailFooter">
              <span className="emailTime">{formatDateTime(email.received_at)}</span>
              <MailStatusBadge status={email.status} />
            </div>
          </button>
        ))}
        {!emails.length && <p className="emptyText">No mails found.</p>}
      </div>

      {emails.length > 0 && (
        <div className="paginationRow">
          <span className="paginationInfo">
            Showing {startIndex + 1}–{endIndex} of {emails.length}
          </span>
          <div className="paginationButtons">
            <button
              className="paginationBtn"
              onClick={() => setPage((current) => Math.max(current - 1, 1))}
              disabled={page === 1}
              type="button"
            >
              <ChevronLeft size={14} />
              Prev
            </button>
            <button
              className="paginationBtn"
              onClick={() => setPage((current) => Math.min(current + 1, totalPages))}
              disabled={page === totalPages}
              type="button"
            >
              Next
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
