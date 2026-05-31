import React, { useState, useEffect, useRef } from "react";
import {
  getCandidate,
  ingestDataset,
  runQuery,
  uploadResumes,
  getEvaluationMetrics,
} from "./api.js";

export default function App() {
  const [mainTab, setMainTab] = useState("chat"); // 'chat' or 'analytics'
  const [evalData, setEvalData] = useState(null);
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [files, setFiles] = useState([]);
  const [limit, setLimit] = useState(20);
  const [skipExisting, setSkipExisting] = useState(true);
  const [includeOriginal, setIncludeOriginal] = useState(true);
  const [includeSynthetic, setIncludeSynthetic] = useState(true);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileData, setProfileData] = useState(null);
  const [activeTab, setActiveTab] = useState("extracted"); // 'extracted' or 'pdf'
  const [isThinking, setIsThinking] = useState(false);
  const [candidates, setCandidates] = useState([]);

  const chatEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  // Auto-scroll is intentionally disabled as per user request.
  // The user prefers to manually scroll to view new messages.
  const scrollToBottom = () => {
    // Kept the function definition in case manual triggers are needed later,
    // but removed the automatic useEffect trigger.
  };

  const quickQueries = [
    {
      label: "Python + ML",
      value: "Find candidates with Python and Machine Learning experience.",
    },
    {
      label: "Risk management",
      value:
        "Show INFORMATION-TECHNOLOGY candidates with risk management experience.",
    },
    {
      label: "5+ years",
      value: "Which candidates have more than 5 years of experience?",
    },
    {
      label: "Data Engineer",
      value: "Recommend candidates suitable for a Data Engineer position.",
    },
  ];

  const handleIngest = async () => {
    try {
      setStatus(
        `Ingestion started: Limit ${limit}, Skip ${skipExisting}, Org ${includeOriginal}, AST ${includeSynthetic}`,
      );
      const result = await ingestDataset(
        limit,
        0,
        skipExisting,
        includeOriginal,
        includeSynthetic,
      );
      setStatus(result.message || "Ingestion task queued.");
    } catch (error) {
      setStatus(error.message);
    }
  };

  const handleUpload = async () => {
    if (!files.length) {
      setStatus("Please select PDF files.");
      return;
    }
    try {
      setStatus("Uploading resumes...");
      const result = await uploadResumes(files);
      setStatus(`Uploaded ${result.count || 0} file(s).`);
    } catch (error) {
      setStatus(error.message);
    }
  };

  const handleQuery = async (e, overrideQuery = null) => {
    e?.preventDefault();
    const activeQuery = overrideQuery || query;
    if (!activeQuery.trim()) return;

    const userMessage = { role: "user", content: activeQuery };
    setMessages((prev) => [...prev, userMessage]);
    setQuery("");
    setIsThinking(true);
    setCandidates([]);

    const aiMessageIndex = messages.length + 1;
    let aiResponse = "";
    let currentCandidates = [];

    try {
      await runQuery({ query: activeQuery, top_k: 5 }, (update) => {
        if (update.candidates) {
          currentCandidates = update.candidates;
          setCandidates(currentCandidates);
        }
        if (update.token) {
          setIsThinking(false);
          aiResponse += update.token;
          setMessages((prev) => {
            const next = [...prev];
            next[aiMessageIndex] = {
              role: "assistant",
              content: aiResponse,
              candidates: currentCandidates,
            };
            return next;
          });
        }
      });
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${error.message}`,
          isError: true,
        },
      ]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleOpenProfile = async (resumeId) => {
    setProfileOpen(true);
    setProfileLoading(true);
    setProfileError("");
    setProfileData(null);
    setActiveTab("extracted");
    try {
      const data = await getCandidate(resumeId);
      setProfileData(data);
    } catch (error) {
      setProfileError(error.message || "Failed to load profile.");
    } finally {
      setProfileLoading(false);
    }
  };

  const loadEvaluation = async () => {
    try {
      setStatus("Loading evaluation metrics...");
      const data = await getEvaluationMetrics();
      setEvalData(data);
      setStatus("Metrics loaded.");
    } catch (error) {
      setStatus("Failed to load metrics: " + error.message);
    }
  };

  useEffect(() => {
    if (mainTab === "analytics" && !evalData) {
      loadEvaluation();
    }
  }, [mainTab]);

  const renderChatbot = () => (
    <div className="row g-4">
      <div className="col-12 col-lg-4">
        <div className="surface shadow-sm mb-4">
          <div className="surface-title mb-3 d-flex align-items-center">
            <i className="bi bi-database-fill-gear text-primary fs-4 me-2" />
            <h2>Data Management</h2>
          </div>
          <div className="row g-2 mb-3">
            <div className="col-12">
              <label className="form-label small fw-bold">
                Batch Limit (Max files to process)
              </label>
              <input
                type="number"
                className="form-control"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              />
              <p
                className="text-muted"
                style={{ fontSize: "0.7rem", marginTop: "4px" }}
              >
                How many new files to process in this session.
              </p>
            </div>
          </div>
          <div className="form-check form-switch mb-3">
            <input
              className="form-check-input"
              type="checkbox"
              id="skipExisting"
              checked={skipExisting}
              onChange={(e) => setSkipExisting(e.target.checked)}
            />
            <label
              className="form-check-label small fw-bold"
              htmlFor="skipExisting"
            >
              Smart Resume (Skip processed files)
            </label>
          </div>
          <div className="form-check form-switch mb-1">
            <input
              className="form-check-input"
              type="checkbox"
              id="includeOriginal"
              checked={includeOriginal}
              onChange={(e) => setIncludeOriginal(e.target.checked)}
            />
            <label className="form-check-label small" htmlFor="includeOriginal">
              Include Original Resumes
            </label>
          </div>
          <div className="form-check form-switch mb-3">
            <input
              className="form-check-input"
              type="checkbox"
              id="includeSynthetic"
              checked={includeSynthetic}
              onChange={(e) => setIncludeSynthetic(e.target.checked)}
            />
            <label
              className="form-check-label small"
              htmlFor="includeSynthetic"
            >
              Include Synthetic (AST_*)
            </label>
          </div>
          <button
            className="btn btn-primary w-100 mb-4 shadow-sm"
            onClick={handleIngest}
          >
            <i className="bi bi-play-circle-fill me-2" />
            {skipExisting ? "Start/Resume Ingestion" : "Force Update All"}
          </button>
          <div className="border-top pt-3">
            <label className="form-label small fw-bold mb-2">
              Upload Custom PDF
            </label>
            <div className="input-group input-group-sm mb-2">
              <input
                type="file"
                accept="application/pdf"
                multiple
                className="form-control"
                onChange={(e) => setFiles(Array.from(e.target.files || []))}
              />
            </div>
            <button
              className="btn btn-outline-primary btn-sm w-100"
              onClick={handleUpload}
            >
              <i className="bi bi-file-earmark-arrow-up-fill me-2" /> Upload &
              Index
            </button>
          </div>
        </div>
      </div>

      <div className="col-12 col-lg-8">
        <div className="chat-container border rounded shadow-sm overflow-hidden d-flex flex-column">
          <div
            className="chat-messages flex-grow-1 overflow-auto p-4"
            ref={chatContainerRef}
            style={{ minHeight: "500px" }}
          >
            {messages.length === 0 && (
              <div className="text-center py-5">
                <div
                  className="avatar bot bg-primary mx-auto mb-3"
                  style={{ width: "60px", height: "60px" }}
                >
                  <i className="bi bi-robot fs-2 text-white" />
                </div>
                <h3 className="h5 fw-bold">How can I assist your search?</h3>
                <div className="d-flex flex-wrap justify-content-center gap-2 mt-3">
                  {quickQueries.map((q) => (
                    <button
                      key={q.label}
                      className="btn btn-white btn-sm border rounded-pill px-3 shadow-sm"
                      onClick={(e) => handleQuery(e, q.value)}
                    >
                      {q.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`message-wrapper ${msg.role}`}>
                <div
                  className={`avatar ${msg.role === "user" ? "user bg-secondary" : "bot bg-primary"} shadow-sm`}
                >
                  <i
                    className={`bi ${msg.role === "user" ? "bi-person-fill" : "bi-robot"} text-white`}
                  />
                </div>
                <div className="message-bubble shadow-sm">
                  <div
                    className="message-content"
                    style={{ whiteSpace: "pre-wrap" }}
                  >
                    {msg.content}
                  </div>
                  {msg.candidates && msg.candidates.length > 0 && (
                    <div className="mt-3 border-top pt-2">
                      <p className="small fw-bold mb-2 text-primary d-flex align-items-center">
                        <i className="bi bi-people-fill me-2" /> Key Profiles:
                      </p>
                      <div className="candidate-mini-list">
                        {msg.candidates.map((c) => (
                          <div
                            key={c.resume_id}
                            className="candidate-mini p-2 border rounded bg-white mb-1 d-flex justify-content-between align-items-center shadow-xs"
                          >
                            <div style={{ lineHeight: "1.2" }}>
                              <div className="fw-bold small">
                                {c.name || "Anonymous Candidate"}{" "}
                                <span className="text-primary opacity-75 ms-1">
                                  #{c.resume_id}
                                </span>
                              </div>
                              <div
                                className="text-muted mt-1"
                                style={{ fontSize: "0.75rem" }}
                              >
                                {c.current_role || "IT Professional"}
                              </div>
                            </div>
                            <button
                              className="btn btn-link btn-sm p-0 text-decoration-none fw-bold"
                              onClick={() => handleOpenProfile(c.resume_id)}
                            >
                              View
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isThinking && (
              <div className="message-wrapper assistant">
                <div className="avatar bot bg-primary shadow-sm">
                  <i className="bi bi-robot text-white" />
                </div>
                <div className="message-bubble shadow-sm bg-white border">
                  <div className="d-flex align-items-center text-primary">
                    <div
                      className="spinner-grow spinner-grow-sm me-2"
                      role="status"
                    ></div>
                    <span className="small fw-bold">Analyzing resumes...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <form
            className="chat-input-area p-3 bg-white border-top"
            onSubmit={handleQuery}
          >
            <div className="input-group">
              <input
                type="text"
                className="form-control form-control-lg border-0 bg-light"
                placeholder="Search candidates..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={isThinking}
              />
              <button
                className="btn btn-primary px-4"
                type="submit"
                disabled={isThinking || !query.trim()}
              >
                <i className="bi bi-send-fill" />
              </button>
            </div>
          </form>
        </div>
      </div>

      {candidates.length > 0 && (
        <div className="col-12 mt-5">
          <div className="d-flex align-items-center justify-content-between mb-4">
            <h2 className="h4 fw-bold mb-0 d-flex align-items-center">
              <i className="bi bi-funnel-fill text-primary me-2" /> Matching
              Candidates
            </h2>
            <span className="badge bg-primary rounded-pill px-3">
              {candidates.length} Profiles
            </span>
          </div>
          <div className="candidate-grid">
            {candidates.map((c) => (
              <div
                className="candidate-card bg-white shadow-sm"
                key={c.resume_id}
              >
                <div className="d-flex justify-content-between align-items-start mb-3">
                  <div className="avatar bg-light text-primary">
                    <i className="bi bi-file-earmark-person fs-4" />
                  </div>
                  <span className="text-muted small">#{c.resume_id}</span>
                </div>
                <h3 className="h6 fw-bold mb-1">{c.name || "Anonymous"}</h3>
                <p className="text-primary small mb-2 fw-medium">
                  {c.current_role}
                </p>
                <div className="mb-4 d-flex flex-wrap gap-1">
                  {c.skills?.slice(0, 4).map((s) => (
                    <span key={s} className="chip">
                      {s}
                    </span>
                  ))}
                </div>
                <button
                  className="btn btn-primary btn-sm w-100 rounded-pill"
                  onClick={() => handleOpenProfile(c.resume_id)}
                >
                  View Full Profile
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  const renderAnalytics = () => {
    if (!evalData)
      return (
        <div className="text-center py-5">
          <span className="spinner-border text-primary" />
        </div>
      );
    const { rag_metrics, sample_size } = evalData;
    return (
      <div className="row g-4">
        <div className="col-12 mb-2">
          <div className="d-flex justify-content-between align-items-center">
            <h2 className="h3 fw-bold mb-0">
              <i className="bi bi-bar-chart-line-fill text-primary me-2" /> AI
              Performance Dashboard
            </h2>
            <button
              className="btn btn-primary btn-sm px-4 fw-bold shadow-sm"
              onClick={loadEvaluation}
            >
              <i className="bi bi-arrow-clockwise me-2" />
              Refresh Metrics
            </button>
          </div>
          <p className="text-muted mt-2">
            Core performance indicators for AI Extraction & Search (
            {sample_size} resumes).
          </p>
        </div>

        <div className="col-12">
          <div className="row g-4">
            <div className="col-12 col-md-4">
              <div className="p-4 bg-white rounded-4 shadow-sm border h-100 position-relative">
                <div className="d-flex align-items-center mb-3">
                  <div className="bg-info-subtle p-2 rounded-3 me-3">
                    <i className="bi bi-patch-check-fill text-info fs-4"></i>
                  </div>
                  <div className="text-muted small fw-bold text-uppercase tracking-wider">
                    Extraction Truth
                  </div>
                </div>
                <div className="h2 fw-bold mb-1 text-dark">
                  {rag_metrics.extraction_faithfulness}%
                </div>
                <div className="small text-muted">
                  AI skills vs Source document accuracy
                </div>
              </div>
            </div>

            <div className="col-12 col-md-4">
              <div className="p-4 bg-white rounded-4 shadow-sm border h-100 position-relative">
                <div className="d-flex align-items-center mb-3">
                  <div className="bg-success-subtle p-2 rounded-3 me-3">
                    <i className="bi bi-stars text-success fs-4"></i>
                  </div>
                  <div className="text-muted small fw-bold text-uppercase tracking-wider">
                    Search Precision
                  </div>
                </div>
                <div className="h2 fw-bold mb-1 text-dark">
                  {rag_metrics.retrieval_precision_at_5}%
                </div>
                <div className="small text-muted">
                  Relevance of matching candidates
                </div>
              </div>
            </div>

            <div className="col-12 col-md-4">
              <div className="p-4 bg-white rounded-4 shadow-sm border h-100 position-relative">
                <div className="d-flex align-items-center mb-3">
                  <div className="bg-primary-subtle p-2 rounded-3 me-3">
                    <i className="bi bi-speedometer text-primary fs-4"></i>
                  </div>
                  <div className="text-muted small fw-bold text-uppercase tracking-wider">
                    Response Latency
                  </div>
                </div>
                <div className="h2 fw-bold mb-1 text-dark">
                  {rag_metrics.average_latency_sec}s
                </div>
                <div className="small text-muted">
                  Processing & Generation speed
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="app">
      <header className="hero border-bottom-0 pb-0">
        <div className="container">
          <div className="d-flex justify-content-between align-items-center mb-4">
            <div>
              <span className="eyebrow">
                <i className="bi bi-cpu-fill me-1" /> R&D Engineering
              </span>
              <h1>IT Resume RAG System</h1>
              <p className="sub mb-0">
                AI-powered recruitment analysis for Information Technology
              </p>
            </div>
            <div className="status-pill shadow-sm">
              <i
                className="bi bi-circle-fill me-2"
                style={{ fontSize: "0.5rem", color: "#10b981" }}
              />
              {status || "System Ready"}
            </div>
          </div>
          <ul className="nav nav-tabs border-bottom-0">
            <li className="nav-item">
              <button
                className={`nav-link border-0 border-bottom border-3 bg-transparent px-4 py-3 fw-bold ${mainTab === "chat" ? "border-primary text-primary" : "border-transparent text-muted"}`}
                onClick={() => setMainTab("chat")}
              >
                <i className="bi bi-chat-square-text-fill me-2" /> AI Chatbot &
                Search
              </button>
            </li>
            <li className="nav-item">
              <button
                className={`nav-link border-0 border-bottom border-3 bg-transparent px-4 py-3 fw-bold ${mainTab === "analytics" ? "border-primary text-primary" : "border-transparent text-muted"}`}
                onClick={() => setMainTab("analytics")}
              >
                <i className="bi bi-graph-up-arrow me-2" /> System Evaluation
              </button>
            </li>
          </ul>
        </div>
      </header>

      <div className="container py-4">
        {mainTab === "chat" ? renderChatbot() : renderAnalytics()}
      </div>

      {profileOpen && (
        <div
          className="custom-modal-backdrop d-flex align-items-center justify-content-center p-3"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1050,
            background: "rgba(0,0,0,0.5)",
            backdropFilter: "blur(4px)",
          }}
          onClick={() => setProfileOpen(false)}
        >
          <div
            className="custom-modal bg-white rounded-4 shadow-lg overflow-hidden"
            style={{ zIndex: 1060 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head p-4 d-flex justify-content-between align-items-start border-bottom">
              <div className="d-flex align-items-center">
                <div
                  className="avatar bg-primary text-white me-3"
                  style={{ width: "40px", height: "40px" }}
                >
                  <i className="bi bi-person-fill fs-5" />
                </div>
                <div>
                  <h3 className="h5 fw-bold mb-0">
                    {profileData?.name || "Candidate Profile"}
                  </h3>
                  <p className="text-muted small mb-0">
                    ID: {profileData?.resume_id}
                    {profileData?.email && (
                      <span className="ms-3">
                        <i className="bi bi-envelope-fill me-1" />
                        {profileData.email}
                      </span>
                    )}
                    {profileData?.phone && (
                      <span className="ms-3">
                        <i className="bi bi-telephone-fill me-1" />
                        {profileData.phone}
                      </span>
                    )}
                  </p>
                </div>
              </div>
              <button
                className="btn-close"
                onClick={() => setProfileOpen(false)}
              ></button>
            </div>
            <div className="modal-body p-0 overflow-hidden flex-grow-1">
              <div className="bg-light border-bottom px-4 d-flex">
                <button
                  className={`btn btn-sm px-4 py-2 rounded-0 border-0 ${activeTab === "extracted" ? "bg-white border-start border-end fw-bold text-primary" : "text-muted"}`}
                  onClick={() => setActiveTab("extracted")}
                >
                  Data
                </button>
                <button
                  className={`btn btn-sm px-4 py-2 rounded-0 border-0 ${activeTab === "pdf" ? "bg-white border-start border-end fw-bold text-primary" : "text-muted"}`}
                  onClick={() => setActiveTab("pdf")}
                >
                  PDF
                </button>
              </div>
              <div className="h-100 overflow-auto p-4">
                {profileLoading ? (
                  <p className="text-center p-5">Loading...</p>
                ) : activeTab === "extracted" ? (
                  <div className="row g-4">
                    <div className="col-12 col-md-7">
                      <h4 className="h6 fw-bold text-muted mb-3">Experience</h4>
                      {profileData?.experience?.map((ex, i) => (
                        <div
                          key={i}
                          className="mb-4 border-start ps-3 border-2 border-primary"
                        >
                          <div className="fw-bold">{ex.title}</div>
                          <div className="small text-primary">
                            {ex.company} • {ex.start_date} - {ex.end_date}
                          </div>
                          <ul className="small text-muted mt-2 ps-3">
                            {ex.highlights?.map((h, j) => (
                              <li key={j}>{h}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                    <div className="col-12 col-md-5">
                      <div className="p-3 bg-light rounded mb-4">
                        <h4 className="h6 fw-bold text-muted mb-3">
                          Education
                        </h4>
                        {profileData?.education?.map((ed, i) => (
                          <div key={i} className="mb-2">
                            <div className="fw-bold small">{ed.degree}</div>
                            <div className="text-muted small">
                              {ed.institution} • {ed.year}
                            </div>
                          </div>
                        ))}
                      </div>
                      <h4 className="h6 fw-bold text-muted mb-3">Skills</h4>
                      <div className="d-flex flex-wrap gap-2">
                        {profileData?.skills?.map((s, i) => (
                          <span key={i} className="chip bg-white">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <iframe
                    src={`http://localhost:8000/api/candidates/${profileData?.resume_id}/pdf`}
                    width="100%"
                    height="100%"
                    style={{ border: "none" }}
                    title="PDF"
                  />
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
