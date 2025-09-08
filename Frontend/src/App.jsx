import React, { useState } from "react";

export default function App() {
  const [step, setStep] = useState(1);
  const [topic, setTopic] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [sessionId, setSessionId] = useState("");
  const [report, setReport] = useState({html:"", pdf:""});

  const startSession = async () => {
    const res = await fetch("http://localhost:8000/start_session", {
      method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({user_input: topic})
    });
    const data = await res.json();
    setSessionId(data.session_id);
    setQuestions(data.questions);
    setStep(2);
  };

  const submitAnswers = async () => {
    const res = await fetch("http://localhost:8000/submit_answers", {
      method:"POST", headers:{"Content-Type":"application/json"}, 
      body: JSON.stringify({session_id: sessionId, answers})
    });
    const data = await res.json();
    const reportRes = await fetch("http://localhost:8000/generate_report", {
      method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({refined_topic: data.refined_topic})
    });
    const reportData = await reportRes.json();
    setReport({html: reportData.html_content, pdf: reportData.pdf_path});
    setStep(3);
  };

  return (
    <div style={{padding:20}}>
      {step===1 && (
        <>
          <h1>Enter your research topic</h1>
          <input value={topic} onChange={e=>setTopic(e.target.value)} />
          <button onClick={startSession}>Start</button>
        </>
      )}
      {step===2 && (
        <>
          <h1>Clarifying Questions</h1>
          {questions.map((q,i)=>(
            <div key={i}>
              <p>{q}</p>
              <input onChange={e=>setAnswers({...answers, [q]: e.target.value})} />
            </div>
          ))}
          <button onClick={submitAnswers}>Generate Report</button>
        </>
      )}
      {step===3 && (
        <>
          <h1>Report Preview</h1>
          <iframe srcDoc={report.html} style={{width:"100%", height:"600px"}} />
          <a href={`http://localhost:8000/pdf_download?file_path=${encodeURIComponent(report.pdf)}`} target="_blank" rel="noopener noreferrer">Download PDF</a>
        </>
      )}
    </div>
  );
}
