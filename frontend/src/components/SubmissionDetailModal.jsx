import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, ExternalLink, FileText, ListChecks, Pencil, Send, XCircle } from "lucide-react";
import { docVerificationApi, fetchAuthedFile } from "../api";
import { VerificationStatusBadge } from "./Badges";
import { formatDateTime } from "../utils/date";
import DocumentThumbnail from "./DocumentThumbnail";

function label(value) {
  return String(value || "Unclassified").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function valueText(value) {
  if (value === null || value === undefined || value === "") return "Not found";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function fieldState(extraction, field, issues = []) {
  const explicit = extraction?.field_statuses?.[field]?.status;
  if (explicit) return explicit;
  const value = extraction?.extracted_data?.[field];
  const warnings = extraction?.shape_warnings || [];
  const documentType = label(extraction?.document_type).toLowerCase();
  const fieldLabel = label(field).toLowerCase();
  const issueFound = issues.some((issue) => String(issue).toLowerCase().includes(fieldLabel) || String(issue).toLowerCase().includes(documentType));
  return value === null || value === undefined || value === "" || issueFound || warnings.some((warning) => String(warning).toLowerCase().includes(fieldLabel)) ? "mismatch" : "match";
}

function fileSize(bytes) {
  if (!bytes) return "0 KB";
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function openFile(url) {
  const result = await fetchAuthedFile(url);
  window.open(result.url, "_blank", "noopener,noreferrer");
}

function DocumentPreview({ file }) {
  const [preview, setPreview] = useState(null);
  const isImage = /\.(png|jpe?g|gif|bmp|webp)$/i.test(file?.filename || "");
  const isPdf = /\.pdf$/i.test(file?.filename || "") || file?.content_type === "application/pdf";

  useEffect(() => {
    let url = null;
    let cancelled = false;
    setPreview(null);
    if (!file?.url) return undefined;
    fetchAuthedFile(file.url).then((result) => {
      if (cancelled) return URL.revokeObjectURL(result.url);
      url = result.url;
      setPreview(url);
    }).catch(() => setPreview(""));
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [file]);

  if (!file) return <div className="documentPreviewEmpty">Select a document to preview it.</div>;
  if (preview === null) return <div className="documentPreviewEmpty">Loading preview...</div>;
  if (!preview) return <div className="documentPreviewEmpty">Preview unavailable.</div>;
  if (isImage) return <img alt={file.filename} className="verificationPreviewImage" src={preview} />;
  if (isPdf) return <iframe className="verificationPreviewFrame" src={preview} title={file.filename} />;
  return <div className="documentPreviewEmpty">Use Open to view this file type.</div>;
}

function EditExtractionDialog({ extraction, issues, onClose, onSave }) {
  const [draft, setDraft] = useState(() => Object.entries(extraction?.extracted_data || {}).map(([field, value]) => ({
    field,
    value: value === null || value === undefined ? "" : typeof value === "object" ? JSON.stringify(value) : String(value),
    status: fieldState(extraction, field, issues),
  })));
  const update = (index, key, value) => setDraft((items) => items.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item));

  return <div className="logModal editExtractionOverlay" role="dialog" aria-modal="true">
    <form className="logModalPanel editExtractionDialog" onSubmit={(event) => { event.preventDefault(); onSave(draft); }}>
      <header className="logModalHeader"><div><h2>Edit model extracted details</h2><span>Review the values against the selected document before confirming.</span></div><button aria-label="Close" className="iconAction" onClick={onClose} type="button"><XCircle size={17} /></button></header>
      {draft.length === 0 ? <p className="emptyText">There are no extracted fields to edit.</p> : draft.map((item, index) => <div className="editFieldRow" key={item.field}><label><span>{label(item.field)}</span><input onChange={(event) => update(index, "value", event.target.value)} value={item.value} /></label><label><span>Review state</span><select onChange={(event) => update(index, "status", event.target.value)} value={item.status}><option value="match">Matched</option><option value="mismatch">Mismatch</option></select></label></div>)}
      <div className="actionRow"><button className="secondaryAction" onClick={onClose} type="button">Cancel</button><button className="primaryAction" type="submit"><CheckCircle2 size={15} />Save changes</button></div>
    </form>
  </div>;
}

export default function SubmissionDetailModal({ submissionId, account, onClose, onViewSummary }) {
  const [detail, setDetail] = useState(null);
  const [selectedFilename, setSelectedFilename] = useState("");
  const [draftChanges, setDraftChanges] = useState([]);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const canWrite = account?.role === "admin" || account?.module_access?.document_verification === "write";

  useEffect(() => {
    let cancelled = false;
    setDetail(null); setDraftChanges([]); setError("");
    docVerificationApi.detail(submissionId).then((data) => { if (!cancelled) { setDetail(data); setSelectedFilename(data.files?.[0]?.filename || ""); } }).catch((err) => !cancelled && setError(err.message));
    return () => { cancelled = true; };
  }, [submissionId]);

  const files = detail?.files || [];
  const extractions = detail?.extracted_documents || [];
  const issues = detail?.issues || [];
  const notes = [...issues, ...(detail?.pending_documents || [])];
  const selectedFile = files.find((file) => file.filename === selectedFilename) || files[0] || null;
  const selectedExtraction = extractions.find((item) => item.originalName === selectedFile?.filename) || null;
  const selectedFields = Object.entries(selectedExtraction?.extracted_data || {});
  const confirmedChanges = detail?.manual_changes || [];
  const documentIssueMap = useMemo(() => new Map(extractions.map((item) => [item.originalName, Boolean(item.warning || item.error || item.shape_warnings?.length)])), [extractions]);

  function stageChanges(items) {
    if (!selectedFile || !selectedExtraction) return;
    const changes = items.filter((item) => {
      const previous = selectedExtraction.extracted_data?.[item.field];
      return String(previous ?? "") !== item.value || fieldState(selectedExtraction, item.field, issues) !== item.status;
    }).map((item) => ({ filename: selectedFile.filename, field: item.field, value: item.value, status: item.status }));
    if (!changes.length) { setEditing(false); return; }
    setDraftChanges((existing) => [...existing.filter((item) => item.filename !== selectedFile.filename), ...changes]);
    setEditing(false);
  }

  async function confirmChanges() {
    if (!draftChanges.length) return;
    setSaving(true); setError("");
    try { const updated = await docVerificationApi.confirmManualChanges(submissionId, draftChanges); setDetail(updated); setDraftChanges([]); }
    catch (err) { setError(err.message || "Could not confirm the reviewed changes."); }
    finally { setSaving(false); }
  }

  return <div className="logModal" role="dialog" aria-modal="true"><div className="logModalPanel verificationModalPanel">
    <header className="logModalHeader"><div>{detail && <VerificationStatusBadge status={detail.status} />}<h2>{detail?.candidate_name || "Loading..."}</h2></div><button aria-label="Close" className="iconAction" onClick={onClose} type="button"><XCircle size={17} /></button></header>
    {error && <div className="errorBanner">{error}</div>}
    {detail && <>
      <section className="auditSummary"><div className="auditDecision"><FileText size={20} /><div><strong>{detail.summary || "Awaiting verdict"}</strong><small className="emptyText">Submitted {formatDateTime(detail.created_at)}</small></div></div><dl className="auditMetaGrid"><div><dt><Clock3 size={14} />Last updated</dt><dd>{formatDateTime(detail.updated_at)}</dd></div><div><dt><ListChecks size={14} />Issues found</dt><dd>{issues.length}</dd></div><div><dt><FileText size={14} />Documents</dt><dd>{files.length} <button className="textAction" onClick={() => onViewSummary?.(submissionId)} type="button">Summarise candidate</button></dd></div><div><dt><AlertTriangle size={14} />Pending</dt><dd>{(detail.pending_documents || []).length}</dd></div></dl></section>
      {(notes.length > 0 || confirmedChanges.length > 0) && <section className={`reviewNotesLayout ${confirmedChanges.length ? "withChanges" : ""}`}><div className="modalSection reviewNotesPanel"><div className="modalSectionHeader"><AlertTriangle size={16} /><h3>Review notes</h3></div>{notes.length ? <ul className="reviewNotesList">{notes.map((note, index) => <li className="reviewNoteItem issue" key={`${note}-${index}`}><AlertTriangle size={15} /><span>{note}</span></li>)}</ul> : <p className="emptyText">No review notes were generated.</p>}</div>{confirmedChanges.length > 0 && <div className="modalSection manualChangesPanel"><div className="modalSectionHeader"><CheckCircle2 size={16} /><h3>Changes made by user</h3></div><ul className="reviewNotesList">{confirmedChanges.map((change, index) => <li className="reviewNoteItem" key={`${change.filename}-${change.field}-${index}`}><CheckCircle2 size={15} /><span><strong>{change.filename}</strong>: {label(change.field)} changed to <strong>{valueText(change.to)}</strong> ({change.status === "match" ? "Matched" : "Mismatch"})</span></li>)}</ul></div>}</section>}
      <section className="verificationWorkspace"><aside className="documentGridPane"><div className="modalSectionHeader"><FileText size={16} /><h3>Submitted documents</h3></div>{files.length ? <div className="documentMiniGrid">{files.map((file) => { const extraction = extractions.find((item) => item.originalName === file.filename); const issue = documentIssueMap.get(file.filename); return <button className={`documentMiniCard ${selectedFile?.filename === file.filename ? "selected" : ""}`} key={file.id} onClick={() => setSelectedFilename(file.filename)} type="button"><div className="docThumbWrap"><DocumentThumbnail filename={file.filename} url={file.url} /></div><span className="documentMiniTitle">{label(extraction?.document_type)}</span><span className="documentMiniMeta">{fileSize(file.size_bytes)}</span><span className={issue ? "badge badgeMismatch" : "badge badgeMatch"}>{issue ? "Review" : "Matched"}</span></button>; })}</div> : <p className="emptyText">No documents are available yet.</p>}</aside><div className="documentReviewPane"><div className="documentPreviewPanel"><div className="documentPreviewHeader"><div><strong>{selectedFile?.filename || "No document selected"}</strong><span>{label(selectedExtraction?.document_type)}</span></div>{selectedFile && <button className="secondaryAction" onClick={() => openFile(selectedFile.url)} type="button"><ExternalLink size={14} />Open</button>}</div><div className="verificationPreviewSurface"><DocumentPreview file={selectedFile} /></div></div><section className="modelFieldsPanel"><div className="modelFieldsHeader"><div className="modalSectionHeader"><ListChecks size={16} /><h3>Model extracted details</h3></div>{canWrite && selectedFields.length > 0 && <button className="secondaryAction" onClick={() => setEditing(true)} type="button"><Pencil size={14} />Edit</button>}</div>{selectedFields.length === 0 ? <p className="emptyPanelText">No extracted fields are available for this document yet.</p> : <div className="fieldResultGrid">{selectedFields.map(([field, value]) => { const match = fieldState(selectedExtraction, field, issues) === "match"; const Icon = match ? CheckCircle2 : AlertTriangle; return <div className={`fieldResultCard ${match ? "fieldMatch" : "fieldMismatch"}`} key={field}><div><span>{label(field)}</span><strong>{valueText(value)}</strong></div><span className="fieldResultBadge"><Icon size={14} />{match ? "Matched" : "Mismatch"}</span></div>; })}</div>}{draftChanges.length > 0 && <div className="actionRow confirmChangesRow"><span>{draftChanges.length} reviewed field{draftChanges.length === 1 ? "" : "s"} waiting for confirmation.</span><button className="primaryAction" disabled={saving} onClick={confirmChanges} type="button"><Send size={15} />{saving ? "Confirming..." : "Confirm submission"}</button></div>}</section></div></section>
    </>}
  </div>{editing && <EditExtractionDialog extraction={selectedExtraction} issues={issues} onClose={() => setEditing(false)} onSave={stageChanges} />}</div>;
}
