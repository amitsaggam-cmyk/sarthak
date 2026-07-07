import { useEffect, useState } from "react";
import { RefreshCcw } from "lucide-react";
import { emailsApi } from "../api";
import MailList from "../components/MailList";
import VerificationDetail from "../components/VerificationDetail";

export default function MailsView({
  loading,
  onError,
  onLoadingChange,
  onRefresh,
  refreshSignal,
}) {
  const [emails, setEmails] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [verification, setVerification] = useState(null);
  const [decisionMessage, setDecisionMessage] = useState("");

  // Keep the inbox list warm so the selected detail can change without remounting the shell.
  async function loadEmails() {
    onLoadingChange(true);
    onError("");

    try {
      const data = await emailsApi.list();
      setEmails(data);
    } catch (err) {
      onError(err.message);
    } finally {
      onLoadingChange(false);
    }
  }

  // Opening a mail is the moment the backend marks it as pending, so we refresh the list after.
  async function loadVerification(emailId) {
    if (!emailId) {
      setVerification(null);
      return;
    }

    setDecisionMessage("");
    onError("");

    try {
      const data = await emailsApi.verification(emailId);
      setVerification(data);
      const refreshed = await emailsApi.list();
      setEmails(refreshed);
    } catch (err) {
      onError(err.message);
    }
  }

  function returnToList() {
    setSelectedId(null);
    setVerification(null);
    setDecisionMessage("");
  }

  // Decisions update the audit trail and then rehydrate the selected mail for the reviewer.
  async function saveDecision(decision) {
    if (!verification) return;

    onError("");
    setDecisionMessage("");

    try {
      const result = await emailsApi.decide(verification.email_id, decision);
      setDecisionMessage(result.message);
      await loadEmails();
      await loadVerification(verification.email_id);
    } catch (err) {
      onError(err.message);
    }
  }

  useEffect(() => {
    loadEmails();
  }, [refreshSignal]);

  useEffect(() => {
    loadVerification(selectedId);
  }, [selectedId]);

  return (
    <section className="mailsPage">
      <header className="pageTitleRow">
        <div>
          <p className="eyebrow">HR background verification</p>
          <h1>Mails</h1>
        </div>
        <button
          aria-label="Refresh mails"
          className="iconAction"
          disabled={loading}
          onClick={onRefresh}
          title="Refresh mails"
          type="button"
        >
          <RefreshCcw size={17} className={loading ? "spin" : ""} />
        </button>
      </header>
      {selectedId ? (
        verification ? (
          <VerificationDetail
            verification={verification}
            onBack={returnToList}
            onDecision={saveDecision}
            decisionMessage={decisionMessage}
          />
        ) : (
          <section className="panel emptyState">Loading selected mail...</section>
        )
      ) : (
        <MailList emails={emails} selectedId={selectedId} onSelect={setSelectedId} />
      )}
    </section>
  );
}
