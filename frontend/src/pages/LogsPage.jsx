import { Fragment, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clipboard,
  FileText,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { logsApi } from "../api";
import ProfileDropdown from "../components/ProfileDropdown";

const MODULE_OPTIONS = ["All Modules", "DOC_VERIFICATION", "EMAIL_BGV", "USER_MGMT"];
const ITEMS_PER_PAGE = 8;

function formatUtcDateTime(value) {
  if (!value) return "Not available";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Invalid date";
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "UTC",
  }).format(date);
}

function statusClass(status) {
  if (status === "SUCCESS") return "badge badgeMatch";
  if (status === "FAILED") return "badge badgeMismatch";
  return "workflowBadge workflowPending";
}

function maskSensitiveText(value) {
  return String(value)
    .replace(/\b[A-Z]{5}\d{4}[A-Z]\b/g, "[Redacted]")
    .replace(/\b(?:\d[ -]?){12}\b/g, "[Redacted]");
}

function DetailField({ label, value }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function TraceField({ traceId }) {
  async function copyTraceId() {
    await navigator.clipboard?.writeText(traceId);
  }

  return (
    <button className="auditTraceCopy" onClick={copyTraceId} type="button" title="Copy Trace ID">
      <Clipboard size={14} />
      <span>{traceId}</span>
    </button>
  );
}

function DocVerificationDetails({ details }) {
  const files = Array.isArray(details.files) ? details.files : [];
  const flags = Array.isArray(details.flags) ? details.flags : [];

  return (
    <div className="auditDetailGrid">
      <section className="auditDetailPanel">
        <h3>Candidate Summary</h3>
        <dl className="auditMetaGrid compactAuditMeta">
          <DetailField label="Candidate Name" value={details.candidateName} />
          <DetailField label="Candidate Reference ID" value={details.candidateReferenceId} />
          <DetailField label="Overall Dossier Status" value={details.overallDossierStatus} />
        </dl>
      </section>
      <section className="auditDetailPanel">
        <h3>File Processing List</h3>
        <div className="auditFileList">
          {files.map((file) => (
            <div className={file.passed ? "auditFileItem passed" : "auditFileItem failed"} key={file.fileName}>
              {file.passed ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
              <span>{file.fileName}</span>
              <small>{file.fileType}</small>
            </div>
          ))}
        </div>
      </section>
      <section className="auditDetailPanel auditWidePanel">
        <h3>Flags and Rule Violations</h3>
        <ul className="auditViolationList">
          {flags.map((flag) => (
            <li key={flag}>
              <CircleAlert size={15} />
              <span>{maskSensitiveText(flag)}</span>
            </li>
          ))}
        </ul>
      </section>
      <section className="auditDetailPanel auditWidePanel">
        <h3>Metadata Footer</h3>
        <dl className="auditMetaGrid compactAuditMeta">
          <DetailField label="Execution Duration" value={`${details.executionDurationMs ?? 0} ms`} />
          <DetailField label="Trace ID" value={<TraceField traceId={details.traceId} />} />
        </dl>
      </section>
    </div>
  );
}

function EmailBgvDetails({ details }) {
  const discrepancies = Array.isArray(details.discrepancies) ? details.discrepancies : [];

  return (
    <div className="auditDetailGrid">
      <section className="auditDetailPanel">
        <h3>Email Metadata</h3>
        <dl className="auditMetaGrid compactAuditMeta">
          <DetailField label="Sender Email" value={details.senderEmail} />
          <DetailField label="Recipient Inbox" value={details.recipientInbox} />
          <DetailField label="Subject" value={details.emailSubject} />
        </dl>
      </section>
      <section className="auditDetailPanel">
        <h3>Verification Findings</h3>
        <dl className="auditMetaGrid compactAuditMeta">
          <DetailField label="Candidate Name" value={details.candidateName} />
          <DetailField label="Outcome" value={details.outcome} />
          <DetailField label="Verified Start" value={details.verifiedStartDate} />
          <DetailField label="Verified End" value={details.verifiedEndDate} />
        </dl>
      </section>
      <section className="auditDetailPanel auditWidePanel">
        <h3>Discrepancy List</h3>
        <div className="comparisonTableWrap">
          <table className="comparisonTable auditNestedTable">
            <thead>
              <tr>
                <th>Item</th>
                <th>Claimed</th>
                <th>Verified</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {discrepancies.map((item) => (
                <tr key={item.item}>
                  <td>{item.item}</td>
                  <td>{item.claimed}</td>
                  <td>{item.verified}</td>
                  <td><span className={item.status === "Matched" ? "badge badgeMatch" : "badge badgeMismatch"}>{item.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="auditDetailPanel auditWidePanel">
        <h3>Metadata Footer</h3>
        <dl className="auditMetaGrid compactAuditMeta">
          <DetailField label="Attachment" value={details.attachmentFilename} />
          <DetailField label="Trace ID" value={<TraceField traceId={details.traceId} />} />
        </dl>
      </section>
    </div>
  );
}

function UserMgmtDetails({ details }) {
  return (
    <div className="auditDetailGrid">
      <section className="auditDetailPanel">
        <h3>Target Account Details</h3>
        <dl className="auditMetaGrid compactAuditMeta">
          <DetailField label="Target User Name" value={details.targetUserName} />
          <DetailField label="Target Email" value={details.targetEmail} />
          <DetailField label="Assigned Role" value={details.assignedRole} />
          <DetailField label="Action Type" value={details.actionType} />
        </dl>
      </section>
      <section className="auditDetailPanel">
        <h3>Security Details</h3>
        <dl className="auditMetaGrid compactAuditMeta">
          <DetailField label="Client IP Address" value={details.clientIpAddress} />
          <DetailField label="Geographic Location" value={details.geographicLocation} />
          <DetailField label="Browser/User-Agent" value={details.browserUserAgent} />
        </dl>
      </section>
      <section className="auditDetailPanel auditWidePanel">
        <h3>State Change Data</h3>
        <pre className="auditJsonBlock">{JSON.stringify(details.stateChange, null, 2)}</pre>
      </section>
    </div>
  );
}

function AuditDetails({ log }) {
  if (log.module === "DOC_VERIFICATION") return <DocVerificationDetails details={log.details} />;
  if (log.module === "EMAIL_BGV") return <EmailBgvDetails details={log.details} />;
  return <UserMgmtDetails details={log.details} />;
}

function normalizeAuditLog(log) {
  return {
    id: log.id,
    timestamp: log.timestamp,
    logId: log.log_id || "",
    module: log.module || "",
    action: log.action || "",
    actorName: log.actor_name || "",
    target: log.target || "",
    status: log.status || "",
    details: log.details || {},
  };
}

export default function LogsPage({ account, onLogout, refreshSignal, onLoadingChange, onError }) {
  const [logs, setLogs] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [moduleFilter, setModuleFilter] = useState("All Modules");
  const [expandedLogIds, setExpandedLogIds] = useState(() => new Set());
  const [page, setPage] = useState(1);

  async function loadLogs() {
    onLoadingChange?.(true);
    onError?.("");

    try {
      const data = await logsApi.list();
      setLogs(data.map(normalizeAuditLog));
    } catch (err) {
      onError?.(err.message);
    } finally {
      setLoaded(true);
      onLoadingChange?.(false);
    }
  }

  useEffect(() => {
    loadLogs();
  }, [refreshSignal]);

  useEffect(() => {
    setPage(1);
  }, [searchText, moduleFilter]);

  const filteredLogs = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return logs.filter((log) => {
      const matchesModule = moduleFilter === "All Modules" || log.module === moduleFilter;
      const matchesSearch =
        !query ||
        log.actorName.toLowerCase().includes(query) ||
        log.logId.toLowerCase().includes(query) ||
        log.target.toLowerCase().includes(query);
      return matchesModule && matchesSearch;
    });
  }, [logs, moduleFilter, searchText]);

  const totalPages = Math.ceil(filteredLogs.length / ITEMS_PER_PAGE) || 1;
  const startIndex = (page - 1) * ITEMS_PER_PAGE;
  const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, filteredLogs.length);
  const paginatedLogs = filteredLogs.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  function toggleRow(logId) {
    setExpandedLogIds((current) => {
      const next = new Set(current);
      if (next.has(logId)) {
        next.delete(logId);
      } else {
        next.add(logId);
      }
      return next;
    });
  }

  return (
    <section className="contentPage">
      <div className="pageTitleRow">
        <div>
          <p className="eyebrow">Enterprise audit trail</p>
          <h1>Audit Logs</h1>
        </div>
        <ProfileDropdown account={account} onLogout={onLogout} />
      </div>

      <section className="panel auditControlBar" aria-label="Audit log controls">
        <label className="auditSearchField">
          <Search size={16} />
          <input
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Search by User, Log ID, or Target/Candidate..."
            type="search"
            value={searchText}
          />
        </label>
        <label className="auditModuleSelect">
          <ShieldCheck size={16} />
          <select onChange={(event) => setModuleFilter(event.target.value)} value={moduleFilter}>
            {MODULE_OPTIONS.map((module) => (
              <option key={module} value={module}>{module}</option>
            ))}
          </select>
        </label>
      </section>

      <section className="panel">
        <div className="panelHeader auditTableHeader">
          <FileText size={18} />
          <h2>Activity Register</h2>
          <span>{filteredLogs.length} records</span>
        </div>
        <div className="comparisonTableWrap auditTableWrap">
          <table className="comparisonTable auditLogTable">
            <thead>
              <tr>
                <th aria-label="Expand row"></th>
                <th>Timestamp</th>
                <th>Log ID</th>
                <th>Module Name</th>
                <th>Action</th>
                <th>Actor Name</th>
                <th>Target / Candidate</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {paginatedLogs.map((log) => {
                const isExpanded = expandedLogIds.has(log.logId);
                return (
                  <Fragment key={log.logId}>
                    <tr
                      className={isExpanded ? "clickable auditRow expanded" : "clickable auditRow"}
                      onClick={() => toggleRow(log.logId)}
                    >
                      <td className="auditExpandCell">
                        {isExpanded ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
                      </td>
                      <td>{formatUtcDateTime(log.timestamp)}</td>
                      <td>{log.logId}</td>
                      <td><span className="badge badgeToggle">{log.module}</span></td>
                      <td>{log.action}</td>
                      <td>{log.actorName}</td>
                      <td>{log.target}</td>
                      <td><span className={statusClass(log.status)}>{log.status}</span></td>
                    </tr>
                    {isExpanded && (
                      <tr className="auditDetailRow">
                        <td colSpan={8}>
                          <AuditDetails log={log} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
        {filteredLogs.length > 0 && (
          <div className="paginationRow">
            <span className="paginationInfo">
              Showing {startIndex + 1}–{endIndex} of {filteredLogs.length}
            </span>
            <div className="paginationButtons">
              <button
                className="paginationBtn"
                disabled={page === 1}
                onClick={() => setPage((current) => Math.max(current - 1, 1))}
                type="button"
              >
                <ChevronLeft size={14} />
                Prev
              </button>
              <button
                className="paginationBtn"
                disabled={page === totalPages}
                onClick={() => setPage((current) => Math.min(current + 1, totalPages))}
                type="button"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
        {!loaded && <p className="emptyText">Loading audit logs...</p>}
        {loaded && !filteredLogs.length && <p className="emptyText">No audit logs match the current controls.</p>}
      </section>
    </section>
  );
}
