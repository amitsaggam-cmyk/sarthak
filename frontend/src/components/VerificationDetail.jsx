import { ArrowLeft, Check, ShieldCheck, X } from "lucide-react";
import { downloadAttachment } from "../api";
import { StatusBadge } from "./Badges";

function ComparisonTable({ verification }) {
  return (
    <section className="panel">
      <div className="panelHeader">
        <ShieldCheck size={18} />
        <h2>Exact Field Verification</h2>
      </div>
      <div className="tableScroller">
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Claimed in Email</th>
              <th>Workday File</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {verification.field_results.map((row) => (
              <tr key={row.field}>
                <td>{row.field.replaceAll("_", " ")}</td>
                <td>{row.claimed_value || "Missing"}</td>
                <td>{row.workday_value || "Not found"}</td>
                <td>
                  <StatusBadge match={row.matches} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function VerificationDetail({
  decisionMessage,
  onBack,
  onDecision,
  verification,
}) {
  const claimed = verification.claimed_details || {};
  const workday = verification.workday_details || {};

  return (
    <div className="detailStack">
      <button className="backButton" onClick={onBack} type="button">
        <ArrowLeft size={17} />
        Back to mails
      </button>

      <div className="reviewHeader">
        <div>
          <p className="eyebrow">Human review required</p>
          <h2>{verification.subject}</h2>
          <p>{verification.sender}</p>
        </div>
        <StatusBadge match={verification.all_fields_match} />
      </div>

      <ComparisonTable verification={verification} />

      <section className="twoColumn">
        <div className="panel">
          <h2>Claimed Details</h2>
          <dl className="detailList">
            <div>
              <dt>Name</dt>
              <dd>{claimed.employee_name || "Missing"}</dd>
            </div>
            <div>
              <dt>Date of Joining</dt>
              <dd>{claimed.date_of_joining || "Missing"}</dd>
            </div>
            <div>
              <dt>Last Working Day</dt>
              <dd>{claimed.last_working_day || "Missing"}</dd>
            </div>
          </dl>
        </div>
        <div className="panel">
          <h2>Workday Details</h2>
          <dl className="detailList">
            <div>
              <dt>Name</dt>
              <dd>{workday.employee_name || "Not found"}</dd>
            </div>
            <div>
              <dt>Date of Joining</dt>
              <dd>{workday.date_of_joining || "Not found"}</dd>
            </div>
            <div>
              <dt>Last Working Day</dt>
              <dd>{workday.last_working_day || "Not found"}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="panel">
        <h2>Attachments</h2>
        {verification.attachments?.length ? (
          <div className="attachmentList">
            {verification.attachments.map((attachment) => (
              <button
                className="attachmentItem"
                key={attachment.id}
                onClick={() => downloadAttachment(attachment)}
                type="button"
              >
                <span>{attachment.filename}</span>
                <small>{attachment.content_type || "file"} · {attachment.size_bytes} bytes</small>
              </button>
            ))}
          </div>
        ) : (
          <p className="emptyText">No documents attached.</p>
        )}
      </section>

      <section className="panel">
        <h2>Response Preview</h2>
        <textarea readOnly value={verification.recommended_reply} />
        <div className="actionRow">
          <button className="primaryAction" onClick={() => onDecision("approve_reply")} type="button">
            <Check size={17} />
            Approve
          </button>
          <button className="dangerAction" onClick={() => onDecision("reject_reply")} type="button">
            <X size={17} />
            Reject
          </button>
          {decisionMessage && <span className="decisionMessage">{decisionMessage}</span>}
        </div>
      </section>

      <section className="panel">
        <h2>Original Email</h2>
        <pre>{verification.body}</pre>
      </section>
    </div>
  );
}
