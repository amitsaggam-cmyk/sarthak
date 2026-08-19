import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  FileCheck2,
  FileText,
  Mail,
} from "lucide-react";
import { docVerificationApi, emailsApi } from "../api";
import ProfileDropdown from "../components/ProfileDropdown";
import { formatDateTime } from "../utils/date";

function initials(name) {
  if (!name) return "?";
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function percent(value, total) {
  if (!total) return 0;
  return Math.round((value / total) * 100);
}

function GraphBar({ label, value, total, tone }) {
  const pct = percent(value, total);

  return (
    <div className="toolGraphItem">
      <div className="toolGraphLabel">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <div className="toolGraphTrack" aria-label={`${label}: ${value}`}>
        <span className={`toolGraphFill ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function DashboardPage({ account, onLogout, onNavigate, onError }) {
  const [emails, setEmails] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [emailData, submissionData] = await Promise.all([
          emailsApi.list(),
          docVerificationApi.list(),
        ]);
        if (!cancelled) {
          setEmails(emailData);
          setSubmissions(submissionData);
        }
      } catch (err) {
        if (!cancelled) onError?.(err.message);
      } finally {
        if (!cancelled) setLoaded(true);
      }
    }

    load();
    const interval = setInterval(load, 6000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [onError]);

  const stats = useMemo(() => {
    const mailsProcessed = emails.filter((e) => e.status === "completed").length;
    const mailsNew = emails.filter((e) => e.status === "new").length;
    const mailsPending = emails.filter((e) => e.status === "pending").length;
    const docsVerified = submissions.filter((s) => s.status === "VERIFIED").length;
    const docsNeedsReview = submissions.filter((s) => s.status === "NEEDS_HUMAN_REVIEW").length;
    const docsPending = submissions.filter((s) => s.status !== "VERIFIED").length;

    return {
      mailsProcessed,
      mailsNew,
      mailsPending,
      docsVerified,
      docsNeedsReview,
      docsPending,
    };
  }, [emails, submissions]);

  const attentionItems = useMemo(() => {
    const newMails = emails
      .filter((e) => e.status === "new")
      .map((e) => ({
        id: `mail-${e.id}`,
        title: e.subject,
        subtitle: `${e.sender} - ${formatDateTime(e.received_at)}`,
      }));

    return newMails.slice(0, 5);
  }, [emails]);

  const documentVerificationLogs = useMemo(() => {
    return submissions
      .map((s) => ({
        id: `doc-${s.id}`,
        name: s.candidate_name,
        subtitle: s.verdict_summary || "Document verification",
        status: s.status,
        updatedAt: s.updated_at || s.created_at,
      }))
      .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
      .slice(0, 5);
  }, [submissions]);

  function statusBadgeClass(status) {
    if (["VERIFIED", "completed"].includes(status)) return "badge badgeMatch";
    if (status === "NEEDS_HUMAN_REVIEW") return "badge badgeMismatch";
    if (status === "pending") return "badge badgeToggle";
    return "badge";
  }

  function statusLabel(status) {
    const map = {
      VERIFIED: "Verified",
      NEEDS_HUMAN_REVIEW: "Needs review",
      PROCESSING: "Processing",
      completed: "Completed",
      pending: "Pending",
      new: "New",
    };
    return map[status] || status;
  }

  const docTotal = Math.max(submissions.length, 1);
  const mailTotal = Math.max(stats.mailsNew + stats.mailsPending, 1);

  return (
    <section className="contentPage">
      <div className="pageTitleRow">
        <div>
          <p className="eyebrow">Onboarding</p>
          <h1>Dashboard</h1>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <ProfileDropdown account={account} onLogout={onLogout} />
        </div>
      </div>

      <section className="metricGrid metricGridFour">
        <article className="metricCard">
          <span className="metricIcon success"><FileCheck2 size={18} /></span>
          <div><small>Total Documents Verified</small><strong>{stats.docsVerified}</strong><em>Today</em></div>
        </article>
        <article className="metricCard">
          <span className="metricIcon"><Mail size={18} /></span>
          <div><small>Total Mails Processed</small><strong>{stats.mailsProcessed}</strong><em>Completed reviews</em></div>
        </article>
        <article className="metricCard">
          <span className="metricIcon warning"><AlertTriangle size={18} /></span>
          <div><small>Pending Review of Mails</small><strong>{stats.mailsPending}</strong><em>Needs attention</em></div>
        </article>
        <article className="metricCard">
          <span className="metricIcon danger"><FileText size={18} /></span>
          <div><small>Pending Review of Documents</small><strong>{stats.docsNeedsReview}</strong><em>Needs attention</em></div>
        </article>
      </section>

      <section className="toolGraphGrid">
        <article className="panel toolGraphCard">
          <div className="panelHeader compactHeader">
            <div>
              <h2>Background Verification</h2>
              <p className="emptyText">Active mail workload</p>
            </div>
            <span className="metricIcon"><Mail size={18} /></span>
          </div>
          <GraphBar label="Total new mails" value={stats.mailsNew} total={mailTotal} tone="new" />
          <GraphBar label="Total pending" value={stats.mailsPending} total={mailTotal} tone="pending" />
          <div className="toolGraphFooter">
            <strong>{stats.mailsNew + stats.mailsPending}</strong>
            <span>active mails</span>
          </div>
        </article>

        <article className="panel toolGraphCard">
          <div className="panelHeader compactHeader">
            <div>
              <h2>Document Verification</h2>
              <p className="emptyText">Candidate document status</p>
            </div>
            <span className="metricIcon success"><FileCheck2 size={18} /></span>
          </div>
          <GraphBar label="Total verified" value={stats.docsVerified} total={docTotal} tone="verified" />
          <GraphBar label="Total pending" value={stats.docsPending} total={docTotal} tone="pending" />
          <div className="toolGraphFooter">
            <strong>{submissions.length}</strong>
            <span>candidate records</span>
          </div>
        </article>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1.2fr", gap: 14, marginTop: 14 }}>

        <section
          className="panel"
          onClick={() => onNavigate("mails")}
          style={{ display: "flex", flexDirection: "column", height: "100%", cursor: "pointer" }}
        >
          <div className="panelHeader" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
            <h2>Mails</h2>
            <span className="badge badgeToggle"><Mail size={12} style={{ color: "var(--primary)" }} />{attentionItems.length} new</span>
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            {attentionItems.length === 0 ? (
              <p className="emptyText">No new mails right now.</p>
            ) : (
              attentionItems.map((item) => (
              <div
                className="emailRow"
                key={item.id}
                style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left", width: "100%", cursor: "default" }}
              >
                <span style={{ flex: 1, minWidth: 0 }}>
                        <span className="emailSubject" style={{ display: "block", marginBottom: 4 }}>
                          {item.title}
                        </span>
                        <span 
                          className="emailMeta" 
                          style={{ 
                            display: "block", 
                            whiteSpace: "nowrap", 
                            overflow: "hidden", 
                            textOverflow: "ellipsis" 
                          }}
                        >
                          {item.subtitle}
                        </span>
                      </span>
                    </div>
              ))
            )}
          </div>
          <div style={{ marginTop: "auto", paddingTop: 12 }}>
            <button 
              className="secondaryAction" 
              onClick={(event) => {
                event.stopPropagation();
                onNavigate("mails");
              }}
              style={{ width: "100%", justifyContent: "center" }}
              type="button"
            >
              Open inbox
            </button>
          </div>
        </section>

        <section
          className="panel"
          onClick={() => onNavigate("verification")}
          style={{ display: "flex", flexDirection: "column", height: "100%", cursor: "pointer" }}
        >
          <div className="panelHeader" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
            <h2>Candidates in progress</h2>
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            {!loaded ? (
              <p className="emptyText">Loading...</p>
            ) : documentVerificationLogs.length === 0 ? (
              <p className="emptyText">No candidates yet.</p>
            ) : (
              documentVerificationLogs.map((c) => (
                <div
                  className="emailRow"
                  key={c.id}
                  style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left", cursor: "default" }}
                >
                  <span
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: "50%",
                      background: "var(--primary-soft)",
                      color: "#93c5fd",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 12,
                      fontWeight: 600,
                      flexShrink: 0,
                    }}
                  >
                    {initials(c.name)}
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span className="emailSubject" style={{ display: "block" }}>{c.name}</span>
                    <span className="emailMeta" style={{ display: "block" }}>{c.subtitle}</span>
                  </span>
                  <span className={statusBadgeClass(c.status)}>{statusLabel(c.status)}</span>
                </div>
              ))
            )}
          </div>
          <div style={{ marginTop: "auto", paddingTop: 12 }}>
            <button 
              className="secondaryAction" 
              onClick={(event) => {
                event.stopPropagation();
                onNavigate("verification");
              }}
              style={{ width: "100%", justifyContent: "center" }}
              type="button"
            >
              Open document verification
            </button>
          </div>
        </section>

      </div>
    </section>
  );
}
