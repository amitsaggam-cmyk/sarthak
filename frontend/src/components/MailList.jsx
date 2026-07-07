import { Inbox } from "lucide-react";
import { ProcessingStatusBadge } from "./Badges";
import { formatDateTime } from "../utils/date";

export default function MailList({ emails, selectedId, onSelect }) {
  return (
    <section className="panel inboxPanel">
      <div className="panelHeader">
        <Inbox size={18} />
        <h2>Mails</h2>
      </div>
      <div className="emailList">
        {emails.map((email) => (
          <button
            className={email.id === selectedId ? "emailRow selected" : "emailRow"}
            key={email.id}
            onClick={() => onSelect(email.id)}
            type="button"
          >
            <span className="emailSubject">{email.subject}</span>
            <span className="emailMeta">{email.sender}</span>
            <div className="emailFooter">
              <span className="emailTime">{formatDateTime(email.received_at)}</span>
              <ProcessingStatusBadge status={email.processing_status} />
            </div>
          </button>
        ))}
        {!emails.length && <p className="emptyText">No mails found.</p>}
      </div>
    </section>
  );
}
