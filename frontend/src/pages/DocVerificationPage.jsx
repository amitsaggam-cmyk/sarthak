import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  FileStack,
  ShieldAlert,
  UploadCloud,
  ChevronLeft,
  ChevronRight,
  Cloud,
  FolderUp,
} from "lucide-react";
import { docVerificationApi } from "../api";
import { VerificationStatusBadge } from "../components/Badges";
import ProfileDropdown from "../components/ProfileDropdown";
import SubmissionDetailModal from "../components/SubmissionDetailModal";
import CandidateSummaryView from "../components/CandidateSummaryView";
import { formatDateTime } from "../utils/date";

const POLL_INTERVAL_MS = 4000;
const MAX_FILES = 25;
const itemsPerPage = 8;

export default function DocVerificationPage({ account, onLogout, onError }) {
  const [submissions, setSubmissions] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [summaryId, setSummaryId] = useState(null);
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [files, setFiles] = useState([]);
  const [sourceMode, setSourceMode] = useState("local");
  const [driveUrl, setDriveUrl] = useState("");
  const [fileError, setFileError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const fileInputRef = useRef(null);

  // Check if user has write access to document verification
  const canWrite = account?.role === "admin" || account?.module_access?.document_verification === "write";

  const refresh = useCallback(async () => {
    try {
      const data = await docVerificationApi.list();
      setSubmissions(data);
    } catch (err) {
      onError?.(err.message);
    } finally {
      setLoaded(true);
    }
  }, [onError]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    setPage(1);
  }, [submissions.length]);

  const verifiedCount = submissions.filter((s) => s.status === "VERIFIED").length;
  const reviewCount = submissions.filter((s) => s.status === "NEEDS_HUMAN_REVIEW").length;
  const processingCount = submissions.filter((s) => s.status === "PROCESSING").length;

  function handleFileChange(event) {
    // Accepts a zip archive OR multiple individual files/folders selected together.
    const picked = Array.from(event.target.files || []);
    setFileError("");
    setFiles((prev) => {
      const isDuplicate = (a, b) => a.name === b.name && a.size === b.size && a.lastModified === b.lastModified;
      const merged = [...prev];
      for (const f of picked) {
        if (!merged.some((existing) => isDuplicate(existing, f))) merged.push(f);
      }
      if (merged.length > MAX_FILES) {
        setFileError(`You can attach at most ${MAX_FILES} files. Only the first ${MAX_FILES} were kept.`);
        return merged.slice(0, MAX_FILES);
      }
      return merged;
    });
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removeFile(index) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setFileError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitError("");
    // Both sources end up as the same candidate-level submission in the backend.
    if (sourceMode === "local" && files.length === 0) {
      setSubmitError("Please attach at least one file (zip archive or individual documents).");
      return;
    }
    if (sourceMode === "drive" && !driveUrl.trim()) {
      setSubmitError("Please paste a Google Drive file or folder link.");
      return;
    }
    setSubmitting(true);
    try {
      if (sourceMode === "drive") {
        await docVerificationApi.submitDrive(driveUrl.trim());
      } else {
        await docVerificationApi.submit(files);
      }
      setFiles([]);
      setDriveUrl("");
      setFileError("");
      setShowForm(false);
      await refresh();
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const totalPages = Math.ceil(submissions.length / itemsPerPage) || 1;
  const startIndex = (page - 1) * itemsPerPage;
  const endIndex = Math.min(startIndex + itemsPerPage, submissions.length);
  const paginated = submissions.slice(startIndex, startIndex + itemsPerPage);

  if (summaryId) {
    return <CandidateSummaryView submissionId={summaryId} onBack={() => setSummaryId(null)} onError={onError} />;
  }

  return (
    <section className="contentPage">
      <div className="pageTitleRow">
        <div>
          <p className="eyebrow">Onboarding</p>
          <h1>Document Verification</h1>
        </div>
        <ProfileDropdown account={account} onLogout={onLogout} />
      </div>

      <section className="metricGrid" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        <article className="metricCard">
          <span className="metricIcon"><FileStack size={18} /></span>
          <div><small>Total Processed</small><strong>{submissions.length}</strong></div>
        </article>
        <article className="metricCard">
          <span className="metricIcon success"><CheckCircle2 size={18} /></span>
          <div><small>Verified</small><strong>{verifiedCount}</strong></div>
        </article>
        <article className="metricCard">
          <span className="metricIcon danger"><ShieldAlert size={18} /></span>
          <div><small>Needs Review</small><strong>{reviewCount}</strong></div>
        </article>
        <article className="metricCard">
          <span className="metricIcon warning"><Clock3 size={18} /></span>
          <div><small>Processing</small><strong>{processingCount}</strong></div>
        </article>
      </section>

      {canWrite && showForm && (
        <section className="panel settingsPanel">
          <div className="panelHeader">
            <h2>Upload Candidate Documents</h2>
          </div>
          <form className="authForm" onSubmit={handleSubmit}>
            <div className="userFormGrid">
              <div className="fullSpan">
                <span className="fieldLabel">Document source</span>
                <div className="sourceToggleGroup">
                  <button
                    className={sourceMode === "local" ? "secondaryAction active" : "secondaryAction"}
                    onClick={() => setSourceMode("local")}
                    type="button"
                  >
                    <FolderUp size={15} />
                    Local files
                  </button>
                  <button
                    className={sourceMode === "drive" ? "secondaryAction active" : "secondaryAction"}
                    onClick={() => setSourceMode("drive")}
                    type="button"
                  >
                    <Cloud size={15} />
                    Google Drive
                  </button>
                </div>
              </div>

              {sourceMode === "local" ? (
                <>
                  <label className="fullSpan">
                    Documents (zip archive, or select multiple files/a folder)
                    <input
                      accept=".zip,application/pdf,image/*"
                      disabled={files.length >= MAX_FILES}
                      multiple
                      onChange={handleFileChange}
                      ref={fileInputRef}
                      type="file"
                    />
                  </label>
                  {fileError && <div className="errorBanner fullSpan">{fileError}</div>}
                  {files.length > 0 && (
                    <div className="fullSpan file-chip-list">
                      {files.map((f, i) => (
                        <span className="badge badgeToggle" key={`${f.name}-${f.size}-${f.lastModified}`}>
                          {f.name}
                          <button
                            aria-label={`Remove ${f.name}`}
                            onClick={() => removeFile(i)}
                            style={{ marginLeft: 6, background: "none", border: "none", cursor: "pointer" }}
                            type="button"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <label className="fullSpan">
                  Google Drive file or folder link
                  <input
                    onChange={(e) => setDriveUrl(e.target.value)}
                    placeholder="https://drive.google.com/drive/folders/..."
                    required={sourceMode === "drive"}
                    type="url"
                    value={driveUrl}
                  />
                </label>
              )}
            </div>

            {submitError && <div className="errorBanner">{submitError}</div>}

            <button className="primaryAction authSubmit" disabled={submitting} type="submit">
              {sourceMode === "drive" ? <Cloud size={16} /> : <UploadCloud size={16} />}
              {submitting ? "Submitting..." : "Submit for Verification"}
            </button>
          </form>
        </section>
      )}

      <section className="panel">
        <div className="panelHeader" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>All Candidates</h2>
          {canWrite && (
            <button
              className="primaryAction"
              onClick={() => setShowForm((c) => !c)}
              style={{ minHeight: "34px", padding: "0 12px", fontSize: "13px" }}
              type="button"
            >
              <UploadCloud size={14} />
              {showForm ? "Cancel" : "Upload Documents"}
            </button>
          )}
        </div>

        {!loaded ? (
          <p className="emptyText">Loading...</p>
        ) : submissions.length === 0 ? (
          <p className="emptyText">No document verification submissions have been processed yet.</p>
        ) : (
          <>
            <div className="comparisonTableWrap">
              <table className="comparisonTable">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Status</th>
                    <th>Verdict</th>
                    <th>Submitted</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {paginated.map((s) => (
                    <tr className="clickable" key={s.id} onClick={() => setSelectedId(s.id)}>
                      <td>{s.candidate_name}</td>
                      <td><VerificationStatusBadge status={s.status} /></td>
                      <td>{s.status === "PROCESSING" ? " " : s.verdict_summary || s.status}</td>
                      <td>{formatDateTime(s.created_at)}</td>
                      <td>
                        <button
                          className="paginationBtn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedId(s.id);
                          }}
                          type="button"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="paginationRow">
              <span className="paginationInfo">
                Showing {startIndex + 1} {endIndex} of {submissions.length}
              </span>
              <div className="paginationButtons">
                <button
                  className="paginationBtn"
                  disabled={page === 1}
                  onClick={() => setPage((c) => Math.max(c - 1, 1))}
                  type="button"
                >
                  <ChevronLeft size={14} />
                  Prev
                </button>
                <button
                  className="paginationBtn"
                  disabled={page === totalPages}
                  onClick={() => setPage((c) => Math.min(c + 1, totalPages))}
                  type="button"
                >
                  Next
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {selectedId && (
        <SubmissionDetailModal
          account={account}
          onClose={() => setSelectedId(null)}
          onViewSummary={(submissionId) => {
            setSelectedId(null);
            setSummaryId(submissionId);
          }}
          submissionId={selectedId}
        />
      )}
    </section>
  );
}
