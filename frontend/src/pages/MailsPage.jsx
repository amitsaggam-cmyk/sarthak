import { useEffect, useState } from "react";
import { Clock3, Filter, Inbox, RefreshCcw, X } from "lucide-react";
import { emailsApi, getAttachmentPreview } from "../api";
import MailList from "../components/MailList";
import VerificationDetail from "../components/VerificationDetail";
import ProfileDropdown from "../components/ProfileDropdown";
import { isValidDisplayDate, parseDisplayDate } from "../utils/date";

export default function MailsPage({
  account,
  onLogout,
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
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState(null);

  const [filters, setFilters] = useState({
    status: "all",
    fromDate: "",
    toDate: "",
  });

  // Check if user has write access to background verification
  const canWrite = account?.role === "admin" || account?.module_access?.background_verification === "write";

  const activeFilterCount = [
    filters.status !== "all",
    Boolean(filters.fromDate),
    Boolean(filters.toDate),
  ].filter(Boolean).length;

  const newCount = emails.filter((email) => email.status === "new").length;
  const pendingCount = emails.filter((email) => email.status === "pending").length;
  const completedCount = emails.filter((email) => email.status === "completed").length;
  const totalCount = Math.max(emails.length, 1);

  const filteredEmails = emails.filter((email) => {
    if (filters.status !== "all" && email.status !== filters.status) {
      return false;
    }
    const receivedDate = String(email.received_at || "").slice(0, 10);
    const fromDate = parseDisplayDate(filters.fromDate);
    const toDate = parseDisplayDate(filters.toDate);

    if (fromDate && receivedDate < fromDate) {
      return false;
    }
    if (toDate && receivedDate > toDate) {
      return false;
    }
    return true;
  });

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

  function updateFilter(event) {
    const { name, value } = event.target;
    setFilters((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function clearFilters() {
    setFilters({
      status: "all",
      fromDate: "",
      toDate: "",
    });
  }

  // Decisions update the audit trail and then rehydrate the selected mail for the reviewer.
  async function saveDecision(decision, replyBody, note = "") {
    if (!verification) return;
    onLoadingChange(true);
    onError("");
    setDecisionMessage("");
    try {
      // Passes the edited replyBody downstream directly to the backend SMTP routine
      const result = await emailsApi.decide(verification.email_id, decision, replyBody, note);
      setDecisionMessage(result.message);
      await loadEmails();
      await loadVerification(verification.email_id);
    } catch (err) {
      onError(err.message);
    } finally {
      onLoadingChange(false);
    }
  }

  async function openAttachmentPreview(attachment) {
    onError("");
    try {
      const preview = await getAttachmentPreview(attachment);
      setPreviewAttachment({ ...attachment, ...preview });
    } catch (err) {
      onError(err.message);
    }
  }

  function closeAttachmentPreview() {
    if (previewAttachment?.url) {
      URL.revokeObjectURL(previewAttachment.url);
    }
    setPreviewAttachment(null);
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
          <p className="eyebrow">JADE background verification</p>
          <h1>Mails</h1>
        </div>
        <div className="mailToolbar">
          <button
            aria-label="Filter mails"
            aria-pressed={filtersOpen}
            className={filtersOpen || activeFilterCount ? "iconAction active" : "iconAction"}
            onClick={() => setFiltersOpen((current) => !current)}
            title="Filter mails"
            type="button"
          >
            <Filter size={17} />
            {activeFilterCount > 0 && (
              <span className="filterCount">{activeFilterCount}</span>
            )}
          </button>
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
          <ProfileDropdown account={account} onLogout={onLogout} />
        </div>
      </header>

      {!selectedId && (
        <>
          <section className="metricGrid">
            <article className="metricCard">
              <span className="metricIcon">
                <Inbox size={18} />
              </span>
              <div>
                <small>New</small>
                <strong>{newCount}</strong>
              </div>
            </article>
            <article className="metricCard">
              <span className="metricIcon warning">
                <Clock3 size={18} />
              </span>
              <div>
                <small>Pending Review</small>
                <strong>{pendingCount}</strong>
              </div>
            </article>
            <article className="metricCard">
              <span className="metricIcon success">
                <Inbox size={18} />
              </span>
              <div>
                <small>Completed</small>
                <strong>{completedCount}</strong>
              </div>
            </article>
          </section>

          <section className="panel statusOverview">
            <div className="statusOverviewHeader">
              <span>Review Pipeline</span>
              <strong>{emails.length} total</strong>
            </div>
            <div className="statusBar" aria-label="Mail status distribution">
              <span className="statusSegment new" style={{ width: `${(newCount / totalCount) * 100}%` }} />
              <span className="statusSegment pending" style={{ width: `${(pendingCount / totalCount) * 100}%` }} />
              <span className="statusSegment completed" style={{ width: `${(completedCount / totalCount) * 100}%` }} />
            </div>
            <div className="statusLegend">
              <span><i className="legendDot new" />New</span>
              <span><i className="legendDot pending" />Pending</span>
              <span><i className="legendDot completed" />Completed</span>
            </div>
          </section>
        </>
      )}

      {selectedId ? (
        verification ? (
          <VerificationDetail
            verification={verification}
            onBack={returnToList}
            onDecision={saveDecision}
            decisionMessage={decisionMessage}
            onPreviewAttachment={openAttachmentPreview}
            canWrite={canWrite}
          />
        ) : (
          <section className="panel emptyState">Loading selected mail...</section>
        )
      ) : (
        <>
          {filtersOpen && (
            <section className="panel filterPanel">
              <div className="filterControls">
                <label>
                  Status
                  <select name="status" onChange={updateFilter} value={filters.status}>
                    <option value="all">All statuses</option>
                    <option value="new">New</option>
                    <option value="pending">Pending</option>
                    <option value="completed">Completed</option>
                  </select>
                </label>
                <label>
                  From
                  <input
                    name="fromDate"
                    onChange={updateFilter}
                    placeholder="DD/MM/YYYY"
                    type="text"
                    value={filters.fromDate}
                  />
                  {!isValidDisplayDate(filters.fromDate) && <span className="fieldHint error">Use DD/MM/YYYY</span>}
                </label>
                <label>
                  To
                  <input
                    name="toDate"
                    onChange={updateFilter}
                    placeholder="DD/MM/YYYY"
                    type="text"
                    value={filters.toDate}
                  />
                  {!isValidDisplayDate(filters.toDate) && <span className="fieldHint error">Use DD/MM/YYYY</span>}
                </label>
                <button
                  className="filterClear"
                  disabled={!activeFilterCount}
                  onClick={clearFilters}
                  type="button"
                >
                  <X size={15} />
                  Clear
                </button>
              </div>
            </section>
          )}
          <MailList emails={filteredEmails} selectedId={selectedId} onSelect={setSelectedId} />
        </>
      )}

      {previewAttachment && (
        <div className="logModal" onClick={closeAttachmentPreview} role="dialog" aria-modal="true">
          <div className="logModalPanel attachmentPreviewPanel" onClick={(event) => event.stopPropagation()}>
            <header className="logModalHeader">
              <div>
                <h2>{previewAttachment.filename}</h2>
              </div>
              <button
                aria-label="Close preview"
                className="iconAction"
                onClick={closeAttachmentPreview}
                title="Close"
                type="button"
              >
                <X size={17} />
              </button>
            </header>
            <div className="attachmentPreviewBody">
              {previewAttachment.contentType?.startsWith("image/") ? (
                <img alt={previewAttachment.filename} src={previewAttachment.url} />
              ) : previewAttachment.contentType === "application/pdf" ? (
                <iframe src={previewAttachment.url} title={previewAttachment.filename} />
              ) : (
                <p className="emptyPanelText">
                  This file type can't be previewed inline. Please download it instead.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}