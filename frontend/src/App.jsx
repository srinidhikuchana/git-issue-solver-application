import { useMemo, useState } from "react";
import {
  Github,
  Search,
  Bug,
  Image as ImageIcon,
  Brain,
  Code2,
  CheckCircle2,
  Upload,
  ExternalLink,
  Sparkles,
  ArrowLeft,
} from "lucide-react";

const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [repoData, setRepoData] = useState(null);
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [solution, setSolution] = useState(null);

  const [loadingRepo, setLoadingRepo] = useState(false);
  const [loadingIssue, setLoadingIssue] = useState(false);
  const [error, setError] = useState("");

  const [showScreenshot, setShowScreenshot] = useState(false);
  const [image, setImage] = useState(null);
  const [imageNote, setImageNote] = useState("");
  const [visionResult, setVisionResult] = useState("");
  const [visionLoading, setVisionLoading] = useState(false);

  const sortedIssues = useMemo(() => {
    if (!repoData?.issues) return [];
    return [...repoData.issues].sort((a, b) => {
      const aScore = a.ai?.contributor_friendliness ?? 0;
      const bScore = b.ai?.contributor_friendliness ?? 0;
      return bScore - aScore;
    });
  }, [repoData]);

  async function readJson(response) {
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.detail || `Request failed (${response.status})`);
    }

    return data;
  }

  async function analyzeRepo() {
    if (!repoUrl.trim()) {
      setError("Paste a public GitHub repository URL first.");
      return;
    }

    setError("");
    setLoadingRepo(true);
    setRepoData(null);
    setSelectedIssue(null);
    setSolution(null);

    try {
      const response = await fetch(`${API}/api/repository/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl.trim() }),
      });

      setRepoData(await readJson(response));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingRepo(false);
    }
  }

  async function solveIssue(issue) {
    setSelectedIssue(issue);
    setSolution(null);
    setError("");
    setLoadingIssue(true);

    try {
      const response = await fetch(`${API}/api/issue/solve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl.trim(),
          issue_number: issue.number,
        }),
      });

      setSolution(await readJson(response));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingIssue(false);
    }
  }

  async function analyzeScreenshot() {
    if (!image) {
      setError("Choose a screenshot first.");
      return;
    }

    setError("");
    setVisionResult("");
    setVisionLoading(true);

    const form = new FormData();
    form.append("image", image);

    if (repoUrl.trim()) {
      form.append("repo_url", repoUrl.trim());
    }
    if (imageNote.trim()) {
      form.append("note", imageNote.trim());
    }

    try {
      const response = await fetch(`${API}/api/vision/debug`, {
        method: "POST",
        body: form,
      });

      const data = await readJson(response);
      setVisionResult(data.analysis || "No analysis returned.");
    } catch (err) {
      setError(err.message);
    } finally {
      setVisionLoading(false);
    }
  }

  return (
    <div className="app">
      <nav className="navbar">
        <div className="brand">
          <div className="logo"><Code2 size={24} /></div>
          <div>
            <h1>OpenFix AI</h1>
            <span>Open-source contribution copilot</span>
          </div>
        </div>

        <div className="modelBadge">
          <Sparkles size={14} />
          Open-weight AI
        </div>
      </nav>

      <section className="hero">
        <div className="heroTag">
          <Github size={15} />
          Built for open-source contributors
        </div>

        <h2>
          Paste a repository.
          <br />
          <span>Find your next contribution.</span>
        </h2>

        <p>
          OpenFix analyzes a public GitHub repository, triages open issues,
          inspects relevant source files, and generates an evidence-grounded
          contribution plan.
        </p>

        <div className="repoInput">
          <Github size={20} />
          <input
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") analyzeRepo();
            }}
            placeholder="https://github.com/owner/repository"
          />
          <button onClick={analyzeRepo} disabled={loadingRepo}>
            <Search size={17} />
            {loadingRepo ? "Analyzing..." : "Analyze repository"}
          </button>
        </div>

        <button
          className="screenshotToggle"
          onClick={() => setShowScreenshot((value) => !value)}
        >
          <ImageIcon size={16} />
          {showScreenshot ? "Hide screenshot debugger" : "Optional: debug from a screenshot"}
        </button>
      </section>

      {error && <div className="errorBox">{error}</div>}

      {showScreenshot && (
        <main className="content">
          <section className="card visionCard">
            <div className="sectionTitle">
              <ImageIcon />
              <div>
                <h3>Screenshot debugger</h3>
                <p>
                  Optional route: upload an error screenshot. If a repository URL
                  is already entered above, OpenFix also uses its README and issue
                  titles as context.
                </p>
              </div>
            </div>

            <label className="uploadZone">
              <Upload size={36} />
              <strong>{image ? image.name : "Choose screenshot"}</strong>
              <span>PNG, JPG/JPEG, or WEBP • up to 8 MB</span>
              <input
                hidden
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(e) => setImage(e.target.files?.[0] || null)}
              />
            </label>

            <textarea
              value={imageNote}
              onChange={(e) => setImageNote(e.target.value)}
              placeholder="Optional note: what were you doing when this error appeared?"
            />

            <button
              className="primaryButton"
              onClick={analyzeScreenshot}
              disabled={visionLoading}
            >
              <Brain size={17} />
              {visionLoading ? "Understanding screenshot..." : "Analyze screenshot"}
            </button>

            {visionResult && (
              <div className="visionResult">
                <h4><Sparkles size={17} /> Debugging report</h4>
                <pre>{visionResult}</pre>
              </div>
            )}
          </section>
        </main>
      )}

      <main className="content">
        {!repoData && !loadingRepo && !showScreenshot && (
          <div className="emptyState">
            <Brain size={46} />
            <h3>Start with a public GitHub repository</h3>
            <p>
              The repository URL is the main input. Screenshot debugging is only
              an optional extra.
            </p>
          </div>
        )}

        {repoData && (
          <>
            <section className="card">
              <div className="sectionTitle">
                <Brain />
                <div>
                  <h3>Repository X-Ray</h3>
                  <p>Repository overview generated from GitHub metadata and README context.</p>
                </div>
              </div>

              <div className="metrics">
                <Metric name="Stars" value={repoData.repository.stars ?? 0} />
                <Metric name="Forks" value={repoData.repository.forks ?? 0} />
                <Metric name="Open issues" value={repoData.repository.open_issues ?? 0} />
                <Metric name="Language" value={repoData.repository.language || "N/A"} />
              </div>

              <div className="summary">
                <div className="repoHeading">
                  <div>
                    <h4>{repoData.repository.name}</h4>
                    <p>{repoData.repository.description || "No GitHub description."}</p>
                  </div>

                  <a
                    href={repoData.repository.github_url}
                    target="_blank"
                    rel="noreferrer"
                    className="smallLink"
                  >
                    GitHub <ExternalLink size={14} />
                  </a>
                </div>

                <p>{repoData.ai_summary?.summary}</p>

                {repoData.ai_summary?.tech_stack?.length > 0 && (
                  <div className="skills">
                    {repoData.ai_summary.tech_stack.map((tech) => (
                      <span key={tech}>{tech}</span>
                    ))}
                  </div>
                )}

                <div className="repoMetaLine">
                  <span>License: {repoData.repository.license || "Not detected"}</span>
                  <span>Model: {repoData.model}</span>
                </div>
              </div>
            </section>

            <section className="card">
              <div className="sectionTitle">
                <Bug />
                <div>
                  <h3>AI issue triage</h3>
                  <p>Issues are shown with estimated difficulty and contributor fit.</p>
                </div>
              </div>

              {sortedIssues.length === 0 ? (
                <div className="noIssues">No open issues were found.</div>
              ) : (
                <div className="issues">
                  {sortedIssues.map((issue) => (
                    <article
                      className={
                        selectedIssue?.number === issue.number
                          ? "issue selected"
                          : "issue"
                      }
                      key={issue.number}
                    >
                      <div className="issueTop">
                        <span className="issueNumber">#{issue.number}</span>

                        {issue.ai?.difficulty && (
                          <span className={`difficulty ${issue.ai.difficulty}`}>
                            {issue.ai.difficulty}
                          </span>
                        )}
                      </div>

                      <h4>{issue.title}</h4>

                      {issue.ai?.short_summary && (
                        <p>{issue.ai.short_summary}</p>
                      )}

                      <div className="issueMeta">
                        {issue.ai?.type && <span>{issue.ai.type}</span>}
                        {issue.ai?.priority && <span>{issue.ai.priority} priority</span>}
                        {issue.ai?.contributor_friendliness !== undefined && (
                          <span>{issue.ai.contributor_friendliness}% contributor fit</span>
                        )}
                      </div>

                      {issue.ai?.skills?.length > 0 && (
                        <div className="skills">
                          {issue.ai.skills.map((skill) => (
                            <span key={`${issue.number}-${skill}`}>{skill}</span>
                          ))}
                        </div>
                      )}

                      <button
                        className="solveButton"
                        onClick={() => solveIssue(issue)}
                        disabled={loadingIssue}
                      >
                        <Brain size={16} />
                        Investigate issue
                      </button>
                    </article>
                  ))}
                </div>
              )}
            </section>

            {loadingIssue && (
              <div className="loadingCard">
                <Brain size={30} />
                <div>
                  <strong>OpenFix is inspecting likely source files...</strong>
                  <span>This may take a little longer than repository triage.</span>
                </div>
              </div>
            )}

            {solution && <SolutionCard result={solution} />}
          </>
        )}
      </main>

      <footer>
        OpenFix AI • Open-weight AI is central to repository analysis and visual debugging.
        Review and test all generated patches before submitting them.
      </footer>
    </div>
  );
}

function Metric({ name, value }) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{name}</span>
    </div>
  );
}

function SolutionCard({ result }) {
  const solution = result.solution || {};
  const rootCause = solution.root_cause || {};

  return (
    <section className="card solutionCard">
      <div className="sectionTitle">
        <Sparkles />
        <div>
          <h3>Contribution plan</h3>
          <p>Grounded in the repository source files that OpenFix actually loaded.</p>
        </div>
      </div>

      <div className="solutionBlock">
        <h4>Issue summary</h4>
        <p>{solution.issue_summary || "No summary returned."}</p>
      </div>

      <div className="solutionBlock">
        <h4>Root cause / best hypothesis</h4>
        <p>{rootCause.explanation || "No root-cause explanation returned."}</p>
        <span className="confidence">
          Confidence: {Number.isFinite(rootCause.confidence) ? rootCause.confidence : 0}%
        </span>
      </div>

      <div className="solutionBlock">
        <h4>Files inspected</h4>
        {result.files_inspected?.length ? (
          result.files_inspected.map((file) => (
            <code className="file" key={file}>{file}</code>
          ))
        ) : (
          <p>No source file contents were successfully loaded.</p>
        )}
      </div>

      <div className="solutionBlock">
        <h4>Fix plan</h4>
        <ol>
          {(solution.fix_plan || []).map((step, index) => (
            <li key={index}>{step}</li>
          ))}
        </ol>
      </div>

      {solution.suggested_patch && (
        <div className="solutionBlock">
          <h4>Suggested patch</h4>
          <pre className="patch">{solution.suggested_patch}</pre>
        </div>
      )}

      <div className="solutionBlock">
        <h4>Testing steps</h4>
        <ul>
          {(solution.testing_steps || []).map((step, index) => (
            <li key={index}>{step}</li>
          ))}
        </ul>
      </div>

      <div className="solutionBlock">
        <h4>Contribution checklist</h4>
        {(solution.contribution_checklist || []).map((item, index) => (
          <div className="checkItem" key={index}>
            <CheckCircle2 size={17} />
            {item}
          </div>
        ))}
      </div>

      {solution.limitations?.length > 0 && (
        <div className="solutionBlock">
          <h4>Limitations</h4>
          <ul>
            {solution.limitations.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {result.issue?.url && (
        <a
          className="githubLink"
          href={result.issue.url}
          target="_blank"
          rel="noreferrer"
        >
          View original GitHub issue <ExternalLink size={15} />
        </a>
      )}
    </section>
  );
}

export default App;
