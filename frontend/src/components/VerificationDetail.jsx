import React, { useState, useEffect } from "react";
import { ArrowLeft, Download, Eye, Send } from "lucide-react"; 
import { downloadAttachment } from "../api"; 

export default function VerificationDetail({
  verification,
  onBack,
  onDecision,
  decisionMessage,
  onPreviewAttachment,
  canWrite = false,
}) {
  const [editableReply, setEditableReply] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [submittedEmailId, setSubmittedEmailId] = useState(null);
  const [overriddenFields, setOverriddenFields] = useState(new Set());

  const isCompleted = verification?.status === "completed";
  const actionSubmitted = submittedEmailId === verification?.email_id;
  
  // Lock actions if completed, processing, submitted, OR user lacks write permissions
  const actionLocked = isCompleted || isProcessing || actionSubmitted || !canWrite;

  const hasFieldResults = Boolean(verification?.field_results?.length);
  const hasAttachments = Boolean(verification?.attachments?.length);

  const effectiveAllMatch = hasFieldResults
   ? verification.field_results.every(
       (result) => result.matches || overriddenFields.has(result.field),
     )
   : verification?.all_fields_match;

  function toggleOverride(fieldName) {
    setOverriddenFields((current) => {
      const next = new Set(current);
      if (next.has(fieldName)) {
        next.delete(fieldName);
      } else {
        next.add(fieldName);
      }
      return next;
    });
  }

  // Sync internal text state and clear processing locks when verification shifts or updates
  useEffect(() => {
    if (verification?.recommended_reply) {
      setEditableReply(verification.recommended_reply);
    } else {
      setEditableReply("");
    }
    setIsProcessing(false);
   }, [verification]);

  useEffect(() => {
    setSubmittedEmailId(null);
    setOverriddenFields(new Set());
  }, [verification?.email_id]);

  if (!verification) return null;

  const handleSendReply = () => {
    if (actionLocked) return;
       
    const decisionType = effectiveAllMatch ? "approve_reply" : "reject_reply";
    let note = "";
    if (overriddenFields.size) {
      const overriddenLabels = [...overriddenFields].map((field) => field.replace(/_/g, " "));
      note = `Force-matched despite mismatch: ${overriddenLabels.join(", ")}`;
    }

    setSubmittedEmailId(verification.email_id);
    setIsProcessing(true);
    onDecision(decisionType, editableReply, note);
  };

  return (
    <div className="contentPage">
      {/* Navigation Top Bar */}
      <div className="pageTitleRow">
        <button className="backButton" onClick={onBack} type="button">
          <ArrowLeft size={16} />
          Back to Mails
        </button>
      </div>

      {/* Main Review Header Banner */}
      <header className="reviewHeader">
        <div>
          <h2>{verification.subject}</h2>
          <p>From: {verification.sender}</p>
        </div>
      </header>

      {/* Full-Width Row-Wise Stack Workspace Container */}
      <div className="detailStack">
                 
        {/* Row 1: Field Analysis Matching Grid Panel */}
        <section className="panel">
          <div className="panelHeader">
            <h2>Field Verification</h2>
          </div>
          <div className="matchList">
            {hasFieldResults ? (
              verification.field_results.map((result, idx) => (
                <div key={idx} className="matchRow">
                  <strong style={{ textTransform: "capitalize", minWidth: "180px" }}>
                    {result.field.replace(/_/g, " ")}
                  </strong>
                  <div>
                    <span className="subtleCell">Claimed</span>
                    {result.claimed_value || <span className="emptyText">None</span>}
                  </div>
                  <div>
                    <span className="subtleCell">Workday</span>
                    {result.workday_value || <span className="emptyText">None</span>}
                  </div>
                  
                  {/* Manual override hides automatically if actionLocked (which includes !canWrite) */}
                  {!result.matches && !actionLocked && (
                   <label className="forceMatchToggle" title="Force this field to be treated as matching">
                     <input
                       checked={overriddenFields.has(result.field)}
                       onChange={() => toggleOverride(result.field)}
                       type="checkbox"
                     />
                     Verified Manually
                   </label>
                 )}
                 
                 <span
                   className={`badge ${
                     result.matches || overriddenFields.has(result.field) ? "badgeMatch" : "badgeMismatch"
                   }`}
                 >
                   {result.matches
                    ? "Match"
                     : overriddenFields.has(result.field)
                       ? "Verified Manually"
                      : "Mismatch"}
                 </span>
                </div>
              ))
            ) : (
              <p className="emptyPanelText">No comparison fields available.</p>
            )}
          </div>
        </section>

        {/* Row 2: Raw Incoming Email Text Content Payload */}
        <section className="panel">
          <div className="panelHeader">
            <h2>Original Email</h2>
          </div>
          <pre>{verification.body || "No email body available."}</pre>
          
          {/* Core System Ingestion Attachment List Elements */}
          <div className="attachmentList">
            <span className="eyebrow">Email Attachments</span>
            {hasAttachments ? (
              verification.attachments.map((attachment) => (
                <div key={attachment.id} className="attachmentItem">
                  <div>
                    <strong>{attachment.filename}</strong>
                    <small>{(attachment.size_bytes / 1024).toFixed(1)} KB</small>
                  </div>
                  <div className="attachmentActions">
                    {onPreviewAttachment && (
                      <button 
                         onClick={() => onPreviewAttachment(attachment)}
                         type="button"
                      >
                        <Eye size={14} /> Preview
                      </button>
                    )}
                    <button 
                       onClick={() => downloadAttachment(attachment)}
                       type="button"
                    >
                      <Download size={14} /> Download
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <p className="emptyPanelText">No attachments.</p>
            )}
          </div>
        </section>

        {/* Row 3: Response Preview Workspace Area (Fully Editable + Wired to Outbound SMTP Engine) */}
        <section className="panel">
          <div className="panelHeader">
            <h2>Response Preview</h2>
          </div>
                     
          <textarea 
            value={editableReply} 
            onChange={(e) => setEditableReply(e.target.value)}
            readOnly={actionLocked}
            style={{ minHeight: "220px" }}
          />

          {/* Operational Workflow Status Logic Toggles */}
          {actionLocked ? (
            <div className="actionRow">
              {!canWrite ? (
                <span className="badge badgeToggle">Read-only access</span>
              ) : (
                <span className="badge badgeMatch">Response has been sent</span>
              )}
              {decisionMessage && <span className="decisionMessage">{decisionMessage}</span>}
            </div>
          ) : (
            <div className="actionRow">
              <button 
                 className="primaryAction" 
                 disabled={!verification.is_processed || !editableReply.trim()}
                onClick={handleSendReply} 
                 type="button"
              >
                <Send size={17} />
                Send Reply
              </button>
              {!verification.is_processed && (
                <span className="emptyText">No processed comparison is available yet.</span>
              )}
              {decisionMessage && <span className="decisionMessage">{decisionMessage}</span>}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}