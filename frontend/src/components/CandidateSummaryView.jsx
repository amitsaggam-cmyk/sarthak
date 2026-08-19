import { useEffect, useState } from "react";
import { ArrowLeft, BriefcaseBusiness, GraduationCap } from "lucide-react";
import { docVerificationApi } from "../api";


function Cell({ children }) {
  return <td>{children || "Not available"}</td>;
}


export default function CandidateSummaryView({ submissionId, onBack, onError }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");


  useEffect(() => {
    let cancelled = false;
    docVerificationApi.candidateSummary(submissionId).then((data) => !cancelled && setSummary(data)).catch((err) => {
      if (!cancelled) { setError(err.message); onError?.(err.message); }
    });
    return () => { cancelled = true; };
  }, [submissionId, onError]);


  if (error) return <section className="contentPage"><button className="secondaryAction" onClick={onBack} type="button"><ArrowLeft size={15} />Back to documents</button><div className="errorBanner">{error}</div></section>;
  if (!summary) return <section className="contentPage"><p className="emptyText">Loading candidate summary...</p></section>;


  return <section className="contentPage candidateSummaryPage">
    <div className="pageTitleRow"><div><p className="eyebrow">Document verification</p><h1>{summary.candidate_name}</h1></div><button className="secondaryAction" onClick={onBack} type="button"><ArrowLeft size={15} />Back to documents</button></div>
    <section className="panel candidateSummaryPanel"><div className="panelHeader"><GraduationCap size={18} /><h2>Educational background</h2></div>{summary.education.length === 0 ? <p className="emptyText">No marksheet or degree details were extracted from this submission.</p> : <div className="comparisonTableWrap"><table className="comparisonTable"><thead><tr><th>Qualification</th><th>End / issued</th><th>Marks or grade</th><th>Result</th><th>Source</th></tr></thead><tbody>{summary.education.map((row, index) => <tr key={`${row.source}-${index}`}><Cell>{row.qualification}</Cell><Cell>{row.end_date}</Cell><Cell>{row.marks_or_grade}</Cell><Cell>{row.result}</Cell><Cell>{row.source}</Cell></tr>)}</tbody></table></div>}</section>
    <section className="panel candidateSummaryPanel"><div className="panelHeader"><BriefcaseBusiness size={18} /><h2>Employment history</h2></div>{summary.employment_history.length === 0 ? <p className="emptyText">No employment history was found in UAN, offer letter, or relieving letter documents.</p> : <div className="comparisonTableWrap"><table className="comparisonTable"><thead><tr><th>Employer</th><th>Start date</th><th>End date</th><th>Source of information</th></tr></thead><tbody>{summary.employment_history.map((row, index) => <tr key={`${row.employer_name}-${index}`}><Cell>{row.employer_name}</Cell><Cell>{row.start_date}</Cell><Cell>{row.end_date}</Cell><Cell>{row.source}</Cell></tr>)}</tbody></table></div>}</section>
  </section>;
}



