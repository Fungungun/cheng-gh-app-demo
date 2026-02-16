import { useEffect, useState } from "react";

const LOGIN_URL = "/api/github/login";

export default function App() {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [repos, setRepos] = useState([]);
  const [repoStatus, setRepoStatus] = useState("idle");
  const [repoError, setRepoError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadUser() {
      try {
        const response = await fetch("/api/github/me", {
          credentials: "include"
        });

        if (response.status === 401) {
          if (active) {
            setStatus("anon");
          }
          return;
        }

        if (!response.ok) {
          throw new Error("Failed to load user");
        }

        const data = await response.json();
        if (active) {
          setUser(data);
          setStatus("authed");
        }
      } catch (err) {
        if (active) {
          setError(err.message || "Something went wrong");
          setStatus("error");
        }
      }
    }

    loadUser();
    return () => {
      active = false;
    };
  }, []);

  async function handleLogout() {
    await fetch("/api/logout", { method: "POST", credentials: "include" });
    setUser(null);
    setStatus("anon");
    setRepos([]);
    setRepoStatus("idle");
    setRepoError("");
  }

  async function handleLoadRepos() {
    setRepoStatus("loading");
    setRepoError("");
    try {
      const response = await fetch("/api/github/repos", {
        credentials: "include"
      });

      if (!response.ok) {
        throw new Error("Failed to load repositories");
      }

      const data = await response.json();
      setRepos(data);
      setRepoStatus("ready");
    } catch (err) {
      setRepoError(err.message || "Unable to load repositories");
      setRepoStatus("error");
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <p className="eyebrow">GitHub OAuth App Demo</p>
        <h1>
          Sign in with GitHub,
          <span> without leaving your flow.</span>
        </h1>
        <p className="subtitle">
          A lightweight React + FastAPI sample that exchanges a GitHub OAuth code for
          user details and keeps it in a short-lived demo session.
        </p>
      </header>

      <main className="card">
        {status === "loading" && <p className="status">Checking session...</p>}

        {status === "anon" && (
          <div className="actions">
            <p className="status">No session found. Start a login flow.</p>
            <a className="primary" href={LOGIN_URL}>
              Connect GitHub
            </a>
          </div>
        )}

        {status === "authed" && user && (
          <div className="authed">
            <div className="profile">
              <img src={user.avatar_url} alt={user.login} />
              <div>
                <h2>{user.name || user.login}</h2>
                <p className="meta">@{user.login}</p>
                <p className="meta">{user.email || "Email hidden"}</p>
              </div>
              <button className="secondary" onClick={handleLogout}>
                Sign out
              </button>
            </div>

            <div className="repo-panel">
              <div className="repo-header">
                <h3>Repositories</h3>
                <button
                  className="primary"
                  onClick={handleLoadRepos}
                  disabled={repoStatus === "loading"}
                >
                  {repoStatus === "loading" ? "Loading..." : "Load repositories"}
                </button>
              </div>

              {repoStatus === "error" && <p className="status">{repoError}</p>}

              {repoStatus === "ready" && repos.length === 0 && (
                <p className="status">No repositories found for this account.</p>
              )}

              {repos.length > 0 && (
                <ul className="repo-list">
                  {repos.map((repo) => (
                    <li key={repo.id}>
                      <a href={repo.html_url} target="_blank" rel="noreferrer">
                        {repo.full_name}
                      </a>
                      {repo.private && <span className="pill">Private</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="actions">
            <p className="status">{error}</p>
            <a className="primary" href={LOGIN_URL}>
              Try again
            </a>
          </div>
        )}
      </main>
    </div>
  );
}
