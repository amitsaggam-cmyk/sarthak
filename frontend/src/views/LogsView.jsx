import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { emailsApi, logsApi } from "../api";
import { StatusBadge } from "../components/Badges";
import { formatDateTime } from "../utils/date";

function formatDecision(value) {
  return value === "approve_reply" ? "Approved" : "Rejected";
}

export default function LogsView({ refreshSignal, onLoadingChange, onError }) {
  const [logs, setLogs] = useState([]);
  const [expandedLogId, setExpandedLogId] = useState(null);
  const [verificationByEmail, setVerificationByEmail] = useState({});

  async function loadLogs() {
    onLoadingChange(true);
    onError("");

    try {
      setLogs(await logsApi.list());
    } catch (err) {
      onError(err.message);
    } finally {
      onLoadingChange(false);
    }
  }

  async function toggleLog(log) {
    if (expandedLogId === log.id) {
      setExpandedLogId(null);
      return;
    }

    setExpandedLogId(log.id);

    if (verificationByEmail[log.email_id]) return;

    try {
      const verification = await emailsApi.verification(log.email_id);
      setVerificationByEmail((current) => ({
        ...current,
        [log.email_id]: verification,
      }));
    } catch (err) {
      onError(err.message);
    }
  }

  useEffect(() => {
    loadLogs();
  }, [refreshSignal]);

  return (
    <section className="contentPage">
      <div className="pageTitleRow">
        <div>
          <p className="eyebrow">Audit trail</p>
          <h1>Logs</h1>
        </div>
      </div>
      <section className="panel">
        <div className="panelHeader">
          <h2>Decision Logs</h2>
        </div>
        <div className="logList">
          {logs.map((log) => {
            const isOpen = expandedLogId === log.id;
            const verification = verificationByEmail[log.email_id];
            const ExpandIcon = isOpen ? ChevronDown : ChevronRight;

            return (
              <article className="logItem" key={log.id}>
                <button className="logSummary" onClick={() => toggleLog(log)} type="button">
                  <ExpandIcon size={17} />
                  <span>
                    <strong>{log.user_full_name || "Unknown user"}</strong>
                    <small>{log.user_email || "No email"}</small>
                  </span>
                  <span>{log.email_subject}</span>
                  <span className="decisionText">{formatDecision(log.decision)}</span>
                  <span>{formatDateTime(log.decided_at)}</span>
                </button>

                {isOpen && (
                  <div className="logDropdown">
                    {verification ? (
                      <>
                        <div className="logDropdownHeader">
                          <strong>Match status</strong>
                          <StatusBadge match={verification.all_fields_match} />
                        </div>
                        <div className="matchList">
                          {verification.field_results.map((field) => (
                            <div className="matchRow" key={field.field}>
                              <span>{field.field.replaceAll("_", " ")}</span>
                              <span>{field.claimed_value || "Missing"}</span>
                              <span>{field.workday_value || "Not found"}</span>
                              <StatusBadge match={field.matches} />
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <p className="emptyText">Loading match status...</p>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
        {!logs.length && <p className="emptyText">No approval or rejection logs yet.</p>}
      </section>
    </section>
  );
}
