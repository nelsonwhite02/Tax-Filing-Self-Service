
import { useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");
const TOKEN_KEY = "eirs_admin_access_token";
const BUSINESS_PAGE_SIZE = 100;
const RECONCILIATION_PAGE_SIZE = 200;

async function request(path, { token, ...options } = {}) {
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  const headers = {
    ...(options.body && !isFormData
      ? { "Content-Type": "application/json" }
      : {}),
    ...(options.headers || {}),
  };

  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const raw = await response.text();
  let data = null;

  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = raw;
  }

  if (!response.ok) {
    const detail =
      data && typeof data === "object"
        ? data.detail || data.message
        : data;

    throw new Error(
      typeof detail === "string"
        ? detail
        : detail
          ? JSON.stringify(detail)
          : `Request failed (${response.status})`
    );
  }

  return data;
}

const money = (value) =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));

const number = (value) =>
  new Intl.NumberFormat("en-NG").format(Number(value || 0));

const dateTime = (value) =>
  value ? new Date(value).toLocaleString() : "—";

const dateOnly = (value) =>
  value ? new Date(value).toLocaleDateString() : "—";

const label = (value) =>
  String(value || "—").replaceAll("_", " ");

const list = (value) => (Array.isArray(value) ? value : []);

function Icon({ name }) {
  const paths = {
    overview: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    people: (
      <>
        <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="10" cy="7" r="4" />
        <path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
      </>
    ),
    company: (
      <>
        <rect x="3" y="7" width="18" height="14" rx="2" />
        <path d="M7 7V4h10v3M7 12h.01M12 12h.01M17 12h.01M7 16h.01M12 16h.01M17 16h.01" />
      </>
    ),
    receipt: (
      <>
        <path d="M4 3h16v18l-3-2-3 2-4-2-3 2-3-2z" />
        <path d="M8 8h8M8 12h8M8 16h4" />
      </>
    ),
    chat: (
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z" />
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    logout: (
      <>
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        <path d="m16 17 5-5-5-5M21 12H9" />
      </>
    ),
    arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
    back: <path d="m15 18-6-6 6-6M9 12h12" />,
    refresh: (
      <>
        <path d="M20 7v5h-5M4 17v-5h5" />
        <path d="M5.5 9A7 7 0 0 1 17 5l3 2M4 17l3 2a7 7 0 0 0 11.5-4" />
      </>
    ),
    alert: (
      <>
        <path d="M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.5L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        <path d="M12 9v4M12 17h.01" />
      </>
    ),
    download: (
      <>
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <path d="m7 10 5 5 5-5M12 15V3" />
      </>
    ),
    upload: (
      <>
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <path d="m17 8-5-5-5 5M12 3v12" />
      </>
    ),
    close: <path d="m18 6-12 12M6 6l12 12" />,
  };

  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.overview}
    </svg>
  );
}

function Loading({ text = "Loading records…" }) {
  return (
    <div className="loading">
      <span className="spinner" />
      {text}
    </div>
  );
}

function ErrorBanner({ message, onRetry }) {
  if (!message) return null;

  return (
    <div className="error-banner" role="alert">
      <Icon name="alert" />
      <span>{message}</span>
      {onRetry && (
        <button
          className="button button-light button-small"
          onClick={onRetry}
          type="button"
        >
          Retry
        </button>
      )}
    </div>
  );
}

function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <div className="empty-mark">
        <Icon name="receipt" />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

function StatCard({ title, value, detail, tone = "blue", icon }) {
  return (
    <article className="stat-card">
      <div className={`stat-icon ${tone}`}>
        <Icon name={icon} />
      </div>
      <div className="stat-copy">
        <span>{title}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}

function SearchBox({
  value,
  onChange,
  placeholder = "Search records…",
}) {
  return (
    <label className="search-box">
      <Icon name="search" />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function StatusPill({ value }) {
  const normalized = String(value || "unknown")
    .toLowerCase()
    .replaceAll("_", "-");

  const tone =
    normalized.includes("complete") ||
    normalized.includes("paid") ||
    normalized === "calculated" ||
    normalized === "confirmed" ||
    normalized === "verified"
      ? "success"
      : normalized.includes("await") ||
          normalized.includes("pending") ||
          normalized.includes("progress") ||
          normalized.includes("unmatched")
        ? "warning"
        : normalized.includes("cancel") ||
            normalized.includes("abandon") ||
            normalized.includes("object") ||
            normalized.includes("reject")
          ? "danger"
          : "neutral";

  return <span className={`status-pill ${tone}`}>{label(value)}</span>;
}

function PageHeading({ eyebrow, title, description, actions }) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </div>
  );
}

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const result = await request("/api/admin/login", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      if (!result?.access_token) {
        throw new Error("Login response did not include an access token.");
      }

      onLogin(result.access_token, email.trim());
    } catch (err) {
      setError(err.message || "Unable to sign in.");
    } finally {
      setBusy(false);
      setPassword("");
    }
  }

  return (
    <main className="login-shell">
      <section className="login-visual">
        <div className="brand brand-large">
          <span className="brand-symbol">E</span>
          <span>
            <strong>EIRS</strong>
            <small>EDO STATE INTERNAL REVENUE SERVICE</small>
          </span>
        </div>
        <div className="login-message">
          <span className="eyebrow">ADMINISTRATION PORTAL</span>
          <h1>
            Clear oversight.
            <br />
            <em>Better service.</em>
          </h1>
          <p>
            Manage taxpayer filings, review assessments, and follow the
            taxpayer journey from one secure workspace.
          </p>
        </div>
        <div className="login-footer">
          Edo State · Taxpayer Administration
        </div>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <div className="mobile-brand brand">
            <span className="brand-symbol">E</span>
            <span>
              <strong>EIRS</strong>
              <small>ADMIN PORTAL</small>
            </span>
          </div>
          <div className="eyebrow">WELCOME BACK</div>
          <h2>Sign in to your workspace</h2>
          <p className="muted">
            Use your authorized EIRS administrator account.
          </p>

          <ErrorBanner message={error} />

          <label className="field-label">
            Email address
            <input
              autoComplete="username"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="admin@eirs.gov.ng"
              required
            />
          </label>

          <label className="field-label">
            Password
            <input
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
              required
            />
          </label>

          <button
            className="button button-primary login-button"
            type="submit"
            disabled={busy}
          >
            {busy ? "Signing in…" : "Sign in securely"}
            <Icon name="arrow" />
          </button>

          <p className="login-security">
            Access is restricted to authorized administrators.
          </p>
        </form>
      </section>
    </main>
  );
}

function Overview({ data, loading, error, onRetry, onNavigate }) {
  if (loading && !data) {
    return <Loading text="Loading dashboard overview…" />;
  }

  const byType = data?.by_filing_type || {};
  const max = Math.max(
    1,
    ...Object.values(byType).map((item) => Number(item?.count || 0))
  );

  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE OVERVIEW"
        title="Good day, administrator"
        description="A live view of taxpayer activity and saved tax assessments."
        actions={
          <button className="button button-light" onClick={onRetry}>
            <Icon name="refresh" /> Refresh data
          </button>
        }
      />

      <ErrorBanner message={error} onRetry={onRetry} />

      <div className="stats-grid">
        <StatCard
          title="Registered taxpayers"
          value={number(data?.taxpayers)}
          detail="Taxpayer profiles"
          icon="people"
          tone="blue"
        />
        <StatCard
          title="Conversations"
          value={number(data?.conversations)}
          detail="All channels"
          icon="chat"
          tone="purple"
        />
        <StatCard
          title="Completed conversations"
          value={number(data?.completed_conversations)}
          detail="Questionnaires completed"
          icon="overview"
          tone="green"
        />
        <StatCard
          title="Saved assessments"
          value={number(data?.assessments)}
          detail="Recorded assessments"
          icon="receipt"
          tone="amber"
        />
      </div>

      <div className="overview-grid">
        <section className="panel filing-panel">
          <div className="panel-heading">
            <div>
              <h2>Filing activity</h2>
              <p>Saved assessments grouped by form type</p>
            </div>
            <span className="live-dot">Live data</span>
          </div>

          {["FORM_A", "FORM_H1", "FORM_H3"].map((code) => {
            const item = byType[code] || {
              count: 0,
              net_tax_due: 0,
            };

            return (
              <div className="filing-row" key={code}>
                <div className={`form-badge ${code.toLowerCase()}`}>
                  {code.replace("FORM_", "")}
                </div>
                <div className="filing-main">
                  <div className="filing-label">
                    <strong>
                      {code === "FORM_A"
                        ? "Individual returns"
                        : code === "FORM_H1"
                          ? "Employer returns · H1"
                          : "Employer returns · H3"}
                    </strong>
                    <span>{number(item.count)} assessments</span>
                  </div>
                  <div className="progress-track">
                    <div
                      className={`progress-fill ${code.toLowerCase()}`}
                      style={{
                        width: `${Math.min(
                          100,
                          (Number(item.count || 0) / max) * 100
                        )}%`,
                      }}
                    />
                  </div>
                  <small>Net tax due: {money(item.net_tax_due)}</small>
                </div>
                <button
                  className="icon-button"
                  title={`View ${code} assessments`}
                  onClick={() => onNavigate("assessments", code)}
                >
                  <Icon name="arrow" />
                </button>
              </div>
            );
          })}

          <div className="panel-footnote">
            Figures reflect saved assessments returned by the API; no new tax
            calculations are performed here.
          </div>
        </section>

        <section className="panel quick-panel">
          <div className="panel-heading">
            <div>
              <h2>Quick access</h2>
              <p>Go straight to a register</p>
            </div>
          </div>

          <button className="quick-link" onClick={() => onNavigate("individuals")}>
            <span className="quick-icon blue">
              <Icon name="people" />
            </span>
            <span>
              <strong>Individual taxpayers</strong>
              <small>Profiles and Form A history</small>
            </span>
            <Icon name="arrow" />
          </button>

          <button className="quick-link" onClick={() => onNavigate("employers")}>
            <span className="quick-icon purple">
              <Icon name="company" />
            </span>
            <span>
              <strong>Companies / employers</strong>
              <small>H1 and H3 filings</small>
            </span>
            <Icon name="arrow" />
          </button>

          <button className="quick-link" onClick={() => onNavigate("assessments")}>
            <span className="quick-icon amber">
              <Icon name="receipt" />
            </span>
            <span>
              <strong>Assessment register</strong>
              <small>Search saved tax assessments</small>
            </span>
            <Icon name="arrow" />
          </button>

          <div className="attention-note">
            <Icon name="alert" />
            <span>
              <strong>Employer data status</strong>
              <small>
                Employer register currently contains no H1/H3 employer-name
                answers returned by the API.
              </small>
            </span>
          </div>
        </section>
      </div>
    </>
  );
}

function Assessments({
  data,
  loading,
  error,
  search,
  setSearch,
  onRetry,
  onOpenTaxpayer,
  onOpenConversation,
  filingFilter,
  setFilingFilter,
}) {
  const items = list(data?.items);

  return (
    <>
      <PageHeading
        eyebrow="TAX RECORDS"
        title="Assessment register"
        description="Review saved assessment amounts and filing history. Values shown here are read from existing records."
        actions={
          <button className="button button-light" onClick={onRetry}>
            <Icon name="refresh" /> Refresh
          </button>
        }
      />

      <ErrorBanner message={error} onRetry={onRetry} />

      <section className="panel table-panel">
        <div className="table-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search taxpayer, reference or form…"
          />
          <div className="toolbar-controls">
            <select
              value={filingFilter}
              onChange={(event) => setFilingFilter(event.target.value)}
              aria-label="Filter by form"
            >
              <option value="">All form types</option>
              <option value="FORM_A">Form A · Individual</option>
              <option value="FORM_H1">Form H1 · Employer</option>
              <option value="FORM_H3">Form H3 · Employer</option>
            </select>
            <span className="result-count">
              {number(data?.total ?? items.length)} records
            </span>
          </div>
        </div>

        {loading ? (
          <Loading />
        ) : items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Assessment</th>
                  <th>Taxpayer / contact</th>
                  <th>Tax year</th>
                  <th>Total income</th>
                  <th>Chargeable income</th>
                  <th>Net tax due</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id || a.conversation_id}>
                    <td>
                      <strong>#{a.id ?? "—"}</strong>
                      <small className="cell-sub">
                        {a.form_code || a.filing_type}
                      </small>
                    </td>
                    <td>
                      <button
                        className="text-link"
                        onClick={() =>
                          a.taxpayer?.id && onOpenTaxpayer(a.taxpayer.id)
                        }
                      >
                        {a.taxpayer?.full_name ||
                          `Taxpayer #${a.taxpayer_id}`}
                      </button>
                      <small className="cell-sub">
                        {a.taxpayer?.taxpayer_reference || "—"}
                      </small>
                    </td>
                    <td>{a.tax_year}</td>
                    <td>{money(a.total_income)}</td>
                    <td>{money(a.chargeable_income)}</td>
                    <td className="money-strong">{money(a.net_tax_due)}</td>
                    <td>
                      <StatusPill value={a.calculation_status} />
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        title="Open chatbot session"
                        onClick={() => onOpenConversation(a.conversation_id)}
                      >
                        <Icon name="chat" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No assessments found"
            description="Try another search or form type. Assessments appear here once saved by the existing assessment service."
          />
        )}

        <div className="panel-footnote">
          Amounts are displayed from saved assessment records. The dashboard
          does not recalculate liability.
        </div>
      </section>
    </>
  );
}

function Individuals({
  data,
  loading,
  error,
  search,
  setSearch,
  onRetry,
  onOpen,
}) {
  const items = list(data?.items);

  return (
    <>
      <PageHeading
        eyebrow="TAXPAYER REGISTER"
        title="Individual taxpayers"
        description="Open a taxpayer profile to review Form A assessments and chatbot sessions."
        actions={
          <button className="button button-light" onClick={onRetry}>
            <Icon name="refresh" /> Refresh
          </button>
        }
      />

      <ErrorBanner message={error} onRetry={onRetry} />

      <section className="panel table-panel">
        <div className="table-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search name, phone, reference or occupation…"
          />
          <span className="result-count">
            {number(data?.total ?? items.length)} taxpayers
          </span>
        </div>

        {loading ? (
          <Loading />
        ) : items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Taxpayer</th>
                  <th>Reference</th>
                  <th>Occupation</th>
                  <th>Location</th>
                  <th>Assessments</th>
                  <th>Latest year</th>
                  <th>Account</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <button
                        className="person-cell text-link"
                        onClick={() => onOpen(t.id)}
                      >
                        <span className="avatar">
                          {(t.full_name || "?")
                            .trim()
                            .slice(0, 1)
                            .toUpperCase()}
                        </span>
                        <span>
                          <strong>{t.full_name || "Unnamed taxpayer"}</strong>
                          <small>
                            {t.phone_number ||
                              t.whatsapp_number ||
                              "No phone recorded"}
                          </small>
                        </span>
                      </button>
                    </td>
                    <td>
                      <span className="mono">
                        {t.taxpayer_reference || "—"}
                      </span>
                    </td>
                    <td>{t.occupation || "—"}</td>
                    <td>
                      {[t.city, t.state].filter(Boolean).join(", ") || "—"}
                    </td>
                    <td>
                      <span className="count-badge">
                        {number(t.assessment_count)}
                      </span>
                    </td>
                    <td>{t.latest_tax_year || "—"}</td>
                    <td>
                      <StatusPill
                        value={t.is_active ? "Active" : "Inactive"}
                      />
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        title="View profile"
                        onClick={() => onOpen(t.id)}
                      >
                        <Icon name="arrow" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No individual taxpayers found"
            description="There are no matching Form A taxpayer profiles for this search."
          />
        )}
      </section>
    </>
  );
}

function Employers({
  data,
  loading,
  error,
  search,
  setSearch,
  onRetry,
  onOpenConversation,
}) {
  const items = list(data?.items);
  const [expanded, setExpanded] = useState("");

  return (
    <>
      <PageHeading
        eyebrow="EMPLOYER REGISTER"
        title="Companies & employers"
        description="Employer identities are grouped from H1/H3 answers captured in existing conversations."
        actions={
          <button className="button button-light" onClick={onRetry}>
            <Icon name="refresh" /> Refresh
          </button>
        }
      />

      <ErrorBanner message={error} onRetry={onRetry} />

      <section className="panel table-panel">
        <div className="table-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search employer name…"
          />
          <span className="result-count">
            {number(data?.total ?? items.length)} employers
          </span>
        </div>

        {loading ? (
          <Loading />
        ) : items.length ? (
          <div className="employer-list">
            {items.map((employer) => (
              <article className="employer-card" key={employer.employer_name}>
                <button
                  className="employer-summary"
                  onClick={() =>
                    setExpanded(
                      expanded === employer.employer_name
                        ? ""
                        : employer.employer_name
                    )
                  }
                >
                  <span className="company-avatar">
                    <Icon name="company" />
                  </span>
                  <span className="employer-title">
                    <strong>{employer.employer_name}</strong>
                    <small>
                      {number(
                        employer.filing_count ??
                          list(employer.filings).length
                      )}{" "}
                      related filings ·{" "}
                      {list(employer.tax_years).join(", ") ||
                        "Tax year not recorded"}
                    </small>
                  </span>
                  <span className="employer-contacts">
                    {number(list(employer.taxpayer_contacts).length)} contact(s)
                  </span>
                  <span
                    className={`expand-chevron ${
                      expanded === employer.employer_name ? "expanded" : ""
                    }`}
                  >
                    ⌄
                  </span>
                </button>

                {expanded === employer.employer_name && (
                  <div className="employer-expanded">
                    <div className="contact-chips">
                      {list(employer.taxpayer_contacts).map((c) => (
                        <span
                          className="contact-chip"
                          key={`${c.taxpayer_id}-${c.name}`}
                        >
                          {c.name}
                          {c.phone_number ? ` · ${c.phone_number}` : ""}
                        </span>
                      ))}
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Form</th>
                            <th>Contact person</th>
                            <th>Conversation</th>
                            <th>Status</th>
                            <th>Assessment</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {list(employer.filings).map((f) => (
                            <tr
                              key={`${f.conversation_id}-${f.form_code}`}
                            >
                              <td>
                                <StatusPill value={f.form_code} />
                              </td>
                              <td>
                                {f.taxpayer_name ||
                                  `Taxpayer #${f.taxpayer_id}`}
                              </td>
                              <td>#{f.conversation_id}</td>
                              <td>
                                <StatusPill value={f.conversation_status} />
                              </td>
                              <td>
                                {f.assessment
                                  ? money(f.assessment.net_tax_due)
                                  : "Not assessed"}
                              </td>
                              <td>
                                <button
                                  className="button button-light button-small"
                                  onClick={() =>
                                    onOpenConversation(f.conversation_id)
                                  }
                                >
                                  View transcript
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No employer records yet"
            description="The API currently returns no H1/H3 employer-name answers. This may mean employer forms have not been submitted yet, or those answers are stored under different question fields. No employer records have been invented."
          />
        )}
      </section>
    </>
  );
}

function DetailGrid({ fields }) {
  return (
    <div className="detail-grid">
      {fields.map(([name, value]) => (
        <div className="detail-item" key={name}>
          <span>{name}</span>
          <strong>{value || "—"}</strong>
        </div>
      ))}
    </div>
  );
}

function TaxpayerDetail({
  data,
  loading,
  error,
  onBack,
  onOpenConversation,
  onRetry,
}) {
  if (loading) {
    return (
      <>
        <button className="back-link" onClick={onBack}>
          <Icon name="back" /> Back to individuals
        </button>
        <Loading text="Loading taxpayer profile…" />
      </>
    );
  }

  const t = data?.taxpayer || data?.profile || data || {};
  const assessments = list(data?.assessments || t.assessments);
  const conversations = list(data?.conversations || t.conversations);

  return (
    <>
      <button className="back-link" onClick={onBack}>
        <Icon name="back" /> Back to individuals
      </button>

      <PageHeading
        eyebrow="TAXPAYER PROFILE"
        title={t.full_name || "Taxpayer details"}
        description={t.taxpayer_reference || `Taxpayer #${t.id}`}
        actions={
          <button className="button button-light" onClick={onRetry}>
            <Icon name="refresh" /> Refresh
          </button>
        }
      />

      <ErrorBanner message={error} onRetry={onRetry} />

      <section className="panel profile-panel">
        <div className="profile-hero">
          <span className="avatar avatar-large">
            {(t.full_name || "?").trim().slice(0, 1).toUpperCase()}
          </span>
          <div>
            <h2>{t.full_name || "Unnamed taxpayer"}</h2>
            <p>
              {t.occupation || "Occupation not recorded"} ·{" "}
              {[t.city, t.state].filter(Boolean).join(", ")}
            </p>
          </div>
          <StatusPill value={t.is_active ? "Active" : "Inactive"} />
        </div>
        <DetailGrid
          fields={[
            ["Taxpayer reference", t.taxpayer_reference],
            ["Phone", t.phone_number],
            ["WhatsApp", t.whatsapp_number],
            ["Email", t.email],
            ["Address", t.address],
            ["Registered", dateOnly(t.created_at)],
          ]}
        />
      </section>

      <section className="panel table-panel section-gap">
        <div className="panel-heading">
          <div>
            <h2>Assessment history</h2>
            <p>
              {assessments.length} saved assessment(s), ordered by tax year and
              record
            </p>
          </div>
        </div>

        {assessments.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Assessment</th>
                  <th>Tax year</th>
                  <th>Income</th>
                  <th>Deductions</th>
                  <th>Chargeable income</th>
                  <th>Net tax due</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {assessments.map((a) => (
                  <tr key={a.id || a.conversation_id}>
                    <td>#{a.id ?? "—"}</td>
                    <td>{a.tax_year}</td>
                    <td>{money(a.total_income)}</td>
                    <td>{money(a.total_deductions)}</td>
                    <td>{money(a.chargeable_income)}</td>
                    <td className="money-strong">{money(a.net_tax_due)}</td>
                    <td>
                      <StatusPill value={a.calculation_status} />
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        title="View session"
                        onClick={() => onOpenConversation(a.conversation_id)}
                      >
                        <Icon name="chat" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No saved assessments"
            description="No assessment records were returned for this taxpayer."
          />
        )}
      </section>

      <section className="panel table-panel section-gap">
        <div className="panel-heading">
          <div>
            <h2>Chatbot sessions</h2>
            <p>Open a session to inspect the transcript.</p>
          </div>
        </div>

        {conversations.length ? (
          <div className="session-list">
            {conversations.map((c) => (
              <div
                className="session-row"
                key={c.id || c.conversation_id}
              >
                <span className="session-icon">
                  <Icon name="chat" />
                </span>
                <div className="session-main">
                  <strong>
                    Conversation #{c.id || c.conversation_id}
                  </strong>
                  <small>
                    {label(c.channel)} · Started {dateTime(c.started_at)}
                  </small>
                </div>
                <StatusPill value={c.status} />
                <button
                  className="button button-light button-small"
                  onClick={() =>
                    onOpenConversation(c.id || c.conversation_id)
                  }
                >
                  View transcript
                </button>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No conversation list returned"
            description="The profile endpoint did not return linked conversations for this taxpayer."
          />
        )}
      </section>
    </>
  );
}

function ConversationDetail({ data, loading, error, onBack, onRetry }) {
  if (loading) {
    return (
      <>
        <button className="back-link" onClick={onBack}>
          <Icon name="back" /> Back
        </button>
        <Loading text="Loading conversation transcript…" />
      </>
    );
  }

  const conversation = data?.conversation || data?.session || data || {};
  const answers = list(
    data?.answers || data?.transcript || conversation.answers
  );
  const taxpayer = data?.taxpayer || conversation.taxpayer || {};

  return (
    <>
      <button className="back-link" onClick={onBack}>
        <Icon name="back" /> Back
      </button>

      <PageHeading
        eyebrow="CHATBOT SESSION"
        title={`Conversation #${
          conversation.id || conversation.conversation_id || "—"
        }`}
        description="Review recorded questions and answers in sequence."
        actions={
          <button className="button button-light" onClick={onRetry}>
            <Icon name="refresh" /> Refresh
          </button>
        }
      />

      <ErrorBanner message={error} onRetry={onRetry} />

      <section className="panel conversation-summary">
        <div>
          <span className="eyebrow">TAXPAYER</span>
          <strong>
            {taxpayer.full_name ||
              `Taxpayer #${conversation.taxpayer_id || "—"}`}
          </strong>
          <small>
            {taxpayer.phone_number ||
              taxpayer.whatsapp_number ||
              "Contact not returned"}
          </small>
        </div>
        <div>
          <span className="eyebrow">CHANNEL</span>
          <strong>{label(conversation.channel)}</strong>
        </div>
        <div>
          <span className="eyebrow">STATUS</span>
          <StatusPill value={conversation.status} />
        </div>
        <div>
          <span className="eyebrow">STARTED</span>
          <strong>{dateTime(conversation.started_at)}</strong>
        </div>
      </section>

      <section className="panel transcript-panel">
        <div className="panel-heading">
          <div>
            <h2>Conversation transcript</h2>
            <p>{answers.length} recorded answer(s)</p>
          </div>
        </div>

        {answers.length ? (
          <div className="transcript-list">
            {answers.map((a, index) => {
              const question = a.question || {};
              const prompt =
                a.prompt ||
                a.question_prompt ||
                question.prompt ||
                question.code ||
                a.question_code ||
                `Response ${index + 1}`;

              let answer =
                a.value ??
                a.value_json ??
                a.raw_text ??
                a.transcription ??
                a.media_reference;

              if (answer && typeof answer === "object") {
                answer = answer.value ?? JSON.stringify(answer);
              }

              if (Array.isArray(answer)) {
                answer = answer.join(", ");
              }

              return (
                <article
                  className="transcript-item"
                  key={a.id || `${a.question_id}-${index}`}
                >
                  <div className="transcript-number">{index + 1}</div>
                  <div className="transcript-content">
                    <div className="transcript-question">{prompt}</div>
                    <div className="transcript-answer">
                      {answer === undefined ||
                      answer === null ||
                      answer === ""
                        ? "No text answer recorded"
                        : String(answer)}
                    </div>
                    <div className="transcript-meta">
                      {label(a.input_type)}
                      {a.repeat_group_code
                        ? ` · ${a.repeat_group_code}${
                            a.repeat_instance
                              ? ` #${a.repeat_instance}`
                              : ""
                          }`
                        : ""}{" "}
                      · {dateTime(a.created_at)}
                    </div>
                    {a.transcription &&
                      a.raw_text &&
                      a.transcription !== a.raw_text && (
                        <div className="transcript-extra">
                          <strong>Transcription:</strong> {a.transcription}
                        </div>
                      )}
                    {a.media_reference && (
                      <div className="transcript-extra">
                        <strong>Media reference:</strong>{" "}
                        {a.media_reference}
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="No transcript answers returned"
            description="The conversation exists, but the endpoint did not return answer rows in the expected format."
          />
        )}
      </section>
    </>
  );
}

/* ------------------------------------------------------------
   BUSINESS REGISTER HELPERS
------------------------------------------------------------ */

function csvCell(value) {
  let text = value == null ? "" : String(value);

  // Reduce spreadsheet formula injection risk when opening exported CSVs.
  if (/^[\s]*[=+\-@]/.test(text)) {
    text = `'${text}`;
  }

  return `"${text.replaceAll('"', '""')}"`;
}

function downloadCsv(filename, rows, columns) {
  const content = [
    columns.map((column) => csvCell(column.label)).join(","),
    ...rows.map((row) =>
      columns.map((column) => csvCell(column.value(row))).join(",")
    ),
  ].join("\r\n");

  const blob = new Blob(["\uFEFF", content], {
    type: "text/csv;charset=utf-8;",
  });

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  URL.revokeObjectURL(url);
}

function businessExportColumns() {
  return [
    { label: "Business ID", value: (r) => r.id },
    { label: "Business name", value: (r) => r.business_name },
    { label: "Registration number", value: (r) => r.registration_number },
    { label: "Tax identifier", value: (r) => r.tax_identifier },
    { label: "Phone", value: (r) => r.phone_number },
    { label: "Email", value: (r) => r.email },
    { label: "Address", value: (r) => r.address },
    { label: "City", value: (r) => r.city },
    { label: "State", value: (r) => r.state },
    { label: "Tax year", value: (r) => r.tax_year },
    { label: "Match status", value: (r) => r.match_status },
    { label: "Verification status", value: (r) => r.verification_status },
    { label: "Matched taxpayer ID", value: (r) => r.matched_taxpayer_id },
    { label: "Source name", value: (r) => r.source_name },
    { label: "Source URL", value: (r) => r.source_url },
    { label: "Review notes", value: (r) => r.review_notes },
  ];
}

function businessFiltersToParams({
  search,
  taxYear,
  matchStatus,
  verificationStatus,
  limit,
  offset,
}) {
  const params = new URLSearchParams();

  params.set("limit", String(limit));
  params.set("offset", String(offset));
  params.set("active_only", "true");

  if (search.trim()) params.set("search", search.trim());
  if (taxYear) params.set("tax_year", taxYear);
  if (matchStatus) params.set("match_status", matchStatus);
  if (verificationStatus) {
    params.set("verification_status", verificationStatus);
  }

  return params;
}

/* ------------------------------------------------------------
   BUSINESS REGISTER
------------------------------------------------------------ */

function BusinessRegister({ token }) {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [taxYear, setTaxYear] = useState("");
  const [filingStatus, setFilingStatus] = useState("");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [file, setFile] = useState(null);
  const [previewFileKey, setPreviewFileKey] = useState("");
  const [importPreview, setImportPreview] = useState(null);

  const pageSize = 50;

  const buttonStyle = {
    border: "1px solid #d1d5db",
    borderRadius: 6,
    padding: "8px 12px",
    background: "#fff",
    cursor: "pointer",
  };

  const inputStyle = {
    border: "1px solid #d1d5db",
    borderRadius: 6,
    padding: "9px 10px",
    minWidth: 150,
  };

  function getFileKey(selectedFile) {
    if (!selectedFile) return "";
    return `${selectedFile.name}:${selectedFile.size}:${selectedFile.lastModified}`;
  }

  async function loadRecords(nextPage = 0) {
    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams({
        limit: String(pageSize),
        offset: String(nextPage * pageSize),
      });

      if (search.trim()) {
        params.set("search", search.trim());
      }

      if (taxYear) {
        params.set("tax_year", taxYear);
      }

      if (filingStatus) {
        params.set("filing_status", filingStatus);
      }

      const result = await request(
        `/api/admin/business-register/status-report?${params.toString()}`,
        { token }
      );

      setRecords(Array.isArray(result.items) ? result.items : []);
      setTotal(Number(result.total) || 0);
      setPage(nextPage);
    } catch (err) {
      setError(err.message || "Could not load the Business Register.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRecords(0);
  }, [token, search, taxYear, filingStatus]);

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0] || null;

    setFile(selectedFile);
    setPreviewFileKey("");
    setImportPreview(null);
    setError("");
    setNotice("");
  }

  async function previewImport() {
    if (!file) {
      setError("Select a CSV file first.");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Only CSV files are supported by the current import endpoint.");
      return;
    }

    setBusy(true);
    setError("");
    setNotice("");
    setImportPreview(null);
    setPreviewFileKey("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const result = await request(
        "/api/admin/business-register/import-csv?dry_run=true",
        {
          token,
          method: "POST",
          body: formData,
        }
      );

      setImportPreview(result);
      setPreviewFileKey(getFileKey(file));
      setNotice("Import preview generated. No records have been imported.");
    } catch (err) {
      setError(err.message || "Import preview failed.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport() {
    if (!file || !importPreview) {
      setError("Preview the selected file before importing it.");
      return;
    }

    if (previewFileKey !== getFileKey(file)) {
      setError("The selected file differs from the preview. Preview it again.");
      setImportPreview(null);
      setPreviewFileKey("");
      return;
    }

    const accepted = window.confirm(
      `Import ${importPreview.would_import ?? 0} records from ` +
      `${file.name}? Duplicate rows will be skipped and invalid rows will ` +
      "not be imported."
    );

    if (!accepted) return;

    setBusy(true);
    setError("");
    setNotice("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const result = await request(
        "/api/admin/business-register/import-csv",
        {
          token,
          method: "POST",
          body: formData,
        }
      );

      setNotice(
        `Import complete: ${result.imported ?? 0} imported, ` +
        `${result.duplicates_skipped ?? 0} duplicates skipped, ` +
        `${result.invalid_rows_count ?? 0} invalid rows.`
      );

      setFile(null);
      setPreviewFileKey("");
      setImportPreview(null);

      // Refresh after the import finishes.
      await loadRecords(0);
    } catch (err) {
      setError(err.message || "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  async function exportAll() {
    setBusy(true);
    setError("");

    try {
      const params = new URLSearchParams();

      if (search.trim()) {
        params.set("search", search.trim());
      }

      if (taxYear) {
        params.set("tax_year", taxYear);
      }

      if (filingStatus) {
        params.set("filing_status", filingStatus);
      }

      const query = params.toString();
      const exportUrl =
        `${API_BASE}/api/admin/business-register/export.csv` +
        (query ? `?${query}` : "");

      const response = await fetch(exportUrl, {
        headers: token
          ? { Authorization: `Bearer ${token}` }
          : {},
      });

      if (!response.ok) {
        let message = "Export failed.";

        try {
          const body = await response.json();
          message = body.detail || message;
        } catch {
          // The server may return a non-JSON error response.
        }

        throw new Error(message);
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");

      anchor.href = objectUrl;
      anchor.download = "eirs_business_register.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      // Delay revocation so the browser can begin downloading the file.
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (err) {
      setError(err.message || "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section style={{ padding: 20 }}>
      <h2>Business Register</h2>

      <p>
        <strong>TP Filed:</strong> A reliable taxpayer match exists, and the
        taxpayer has completed the chatbot return process with the tax
        liability calculated and presented. Payment is not required.
        <br />
        <strong>TP Not Filed:</strong> No reliable match exists, or the
        matched taxpayer has not completed that process.
      </p>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          marginBottom: 16,
          alignItems: "center",
        }}
      >
        <input
          style={inputStyle}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search business or individual"
          aria-label="Search business register"
        />

        <input
          style={inputStyle}
          value={taxYear}
          onChange={(event) => setTaxYear(event.target.value)}
          type="number"
          min="2000"
          max="2100"
          placeholder="Tax year"
          aria-label="Tax year"
        />

        <select
          style={inputStyle}
          value={filingStatus}
          onChange={(event) => setFilingStatus(event.target.value)}
          aria-label="Filing status"
        >
          <option value="">All</option>
          <option value="TP_FILED">TP Filed</option>
          <option value="TP_NOT_FILED">TP Not Filed</option>
        </select>

        <button
          type="button"
          style={buttonStyle}
          onClick={() => loadRecords(0)}
          disabled={loading || busy}
        >
          Refresh
        </button>

        <button
          type="button"
          style={buttonStyle}
          onClick={exportAll}
          disabled={busy}
        >
          Export all filtered records
        </button>
      </div>

      <div
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: 14,
          marginBottom: 18,
        }}
      >
        <h3>Bulk import</h3>
        <p>
          Upload a CSV file to preview validation and duplicate checks before
          importing records.
        </p>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            alignItems: "center",
          }}
        >
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={handleFileChange}
            aria-label="Select CSV file to import"
          />

          <button
            type="button"
            style={buttonStyle}
            onClick={previewImport}
            disabled={busy || !file}
          >
            Preview import
          </button>

          {importPreview && (
            <button
              type="button"
              style={buttonStyle}
              onClick={confirmImport}
              disabled={busy || previewFileKey !== getFileKey(file)}
            >
              Confirm import
            </button>
          )}
        </div>

        {file && (
          <p style={{ fontSize: 13, color: "#4b5563" }}>
            Selected file: {file.name}
          </p>
        )}

        {importPreview && (
          <div style={{ marginTop: 12 }}>
            <p>
              <strong>Would import:</strong>{" "}
              {importPreview.would_import ?? 0}
            </p>

            <p>
              <strong>Duplicates skipped:</strong>{" "}
              {importPreview.duplicates_skipped ?? 0}
            </p>

            <p>
              <strong>Invalid rows:</strong>{" "}
              {importPreview.invalid_rows_count ?? 0}
            </p>

            {(importPreview.invalid_rows || []).length > 0 && (
              <details>
                <summary>View invalid rows</summary>
                <ul>
                  {importPreview.invalid_rows.map((row, index) => (
                    <li key={`${row.row ?? "row"}-${index}`}>
                      Row {row.row ?? "unknown"}:{" "}
                      {(row.errors || []).join(", ") || "Invalid row"}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {(importPreview.duplicate_rows || []).length > 0 && (
              <details>
                <summary>View duplicate rows</summary>
                <ul>
                  {importPreview.duplicate_rows.map((row, index) => (
                    <li key={`${row.row ?? "duplicate"}-${index}`}>
                      Row {row.row ?? "unknown"}:{" "}
                      {row.reason || row.message || "Duplicate record"}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </div>

      {error && (
        <p role="alert" style={{ color: "#b91c1c" }}>
          {error}
        </p>
      )}

      {notice && (
        <p role="status" style={{ color: "#166534" }}>
          {notice}
        </p>
      )}

      <p>
        {loading
          ? "Loading records..."
          : `${total.toLocaleString()} matching records`}
      </p>

      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            textAlign: "left",
          }}
        >
          <thead>
            <tr>
              {[
                "Business / Individual",
                "Registration number",
                "Tax identifier",
                "City",
                "Tax year",
                "Status",
              ].map((heading) => (
                <th
                  key={heading}
                  style={{
                    borderBottom: "1px solid #d1d5db",
                    padding: 10,
                    whiteSpace: "nowrap",
                  }}
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {!loading && records.length === 0 && (
              <tr>
                <td colSpan={6} style={{ padding: 16 }}>
                  No records match the selected filters.
                </td>
              </tr>
            )}

            {records.map((record) => {
              const isFiled = record.filing_status === "TP_FILED";

              return (
                <tr key={record.id}>
                  <td
                    style={{
                      padding: 10,
                      borderBottom: "1px solid #eee",
                    }}
                  >
                    {record.business_name || "—"}
                  </td>

                  <td
                    style={{
                      padding: 10,
                      borderBottom: "1px solid #eee",
                    }}
                  >
                    {record.registration_number || "—"}
                  </td>

                  <td
                    style={{
                      padding: 10,
                      borderBottom: "1px solid #eee",
                    }}
                  >
                    {record.tax_identifier || "—"}
                  </td>

                  <td
                    style={{
                      padding: 10,
                      borderBottom: "1px solid #eee",
                    }}
                  >
                    {record.city || "—"}
                  </td>

                  <td
                    style={{
                      padding: 10,
                      borderBottom: "1px solid #eee",
                    }}
                  >
                    {record.tax_year ?? "—"}
                  </td>

                  <td
                    style={{
                      padding: 10,
                      borderBottom: "1px solid #eee",
                    }}
                  >
                    <span
                      style={{
                        display: "inline-block",
                        borderRadius: 5,
                        padding: "4px 8px",
                        background: isFiled ? "#dcfce7" : "#f3f4f6",
                        color: isFiled ? "#166534" : "#374151",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {isFiled ? "TP Filed" : "TP Not Filed"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          justifyContent: "flex-end",
          marginTop: 16,
        }}
      >
        <button
          type="button"
          style={buttonStyle}
          disabled={loading || busy || page === 0}
          onClick={() => loadRecords(page - 1)}
        >
          Previous
        </button>

        <span>
          Page {Math.min(page + 1, totalPages)} of {totalPages}
        </span>

        <button
          type="button"
          style={buttonStyle}
          disabled={loading || busy || (page + 1) * pageSize >= total}
          onClick={() => loadRecords(page + 1)}
        >
          Next
        </button>
      </div>
    </section>
  );
}



export default function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem(TOKEN_KEY) || ""
  );
  const [admin, setAdmin] = useState(null);
  const [active, setActive] = useState("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState(null);
  const [assessments, setAssessments] = useState(null);
  const [individuals, setIndividuals] = useState(null);
  const [employers, setEmployers] = useState(null);
  const [search, setSearch] = useState("");
  const [filingFilter, setFilingFilter] = useState("");
  const [selectedTaxpayer, setSelectedTaxpayer] = useState(null);
  const [taxpayerData, setTaxpayerData] = useState(null);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [conversationData, setConversationData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const navigate = useCallback((page, filter = "") => {
    setActive(page);
    setSearch("");
    setFilingFilter(filter);
    setError("");
    setSelectedTaxpayer(null);
    setSelectedConversation(null);
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken("");
    setAdmin(null);
    setOverview(null);
    setAssessments(null);
    setIndividuals(null);
    setEmployers(null);
    setSelectedTaxpayer(null);
    setTaxpayerData(null);
    setSelectedConversation(null);
    setConversationData(null);
    setActive("overview");
    setSearch("");
    setError("");
  }, []);

  useEffect(() => {
    if (!token) return;

    sessionStorage.setItem(TOKEN_KEY, token);
    let cancelled = false;

    request("/api/admin/me", { token })
      .then((data) => {
        if (!cancelled) setAdmin(data?.user || data);
      })
      .catch(() => {
        if (!cancelled) logout();
      });

    return () => {
      cancelled = true;
    };
  }, [token, logout]);

  const loadPage = useCallback(async () => {
    if (!token) return;
    if (["taxpayer-detail", "conversation-detail"].includes(active)) return;

    setLoading(true);
    setError("");

    try {
      if (active === "overview") {
        setOverview(
          await request("/api/admin/dashboard/overview", { token })
        );
      }

      if (active === "assessments") {
        const params = new URLSearchParams({
          limit: "100",
          offset: "0",
        });

        if (search.trim()) params.set("search", search.trim());
        if (filingFilter) params.set("filing_type", filingFilter);

        setAssessments(
          await request(
            `/api/admin/dashboard/assessments?${params}`,
            { token }
          )
        );
      }

      if (active === "individuals") {
        const params = new URLSearchParams();

        if (search.trim()) params.set("search", search.trim());

        setIndividuals(
          await request(
            `/api/admin/dashboard/individuals${
              params.size ? `?${params}` : ""
            }`,
            { token }
          )
        );
      }

      if (active === "employers") {
        const params = new URLSearchParams();

        if (search.trim()) params.set("search", search.trim());

        setEmployers(
          await request(
            `/api/admin/dashboard/employers${
              params.size ? `?${params}` : ""
            }`,
            { token }
          )
        );
      }
    } catch (err) {
      setError(err.message || "Unable to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, [token, active, search, filingFilter, refreshKey]);

  useEffect(() => {
    loadPage();
  }, [loadPage]);

  const openTaxpayer = useCallback(
    async (id) => {
      setSelectedTaxpayer(id);
      setSelectedConversation(null);
      setActive("taxpayer-detail");
      setDetailLoading(true);
      setDetailError("");
      setTaxpayerData(null);

      try {
        setTaxpayerData(
          await request(`/api/admin/dashboard/taxpayers/${id}`, { token })
        );
      } catch (err) {
        setDetailError(err.message || "Unable to load taxpayer profile.");
      } finally {
        setDetailLoading(false);
      }
    },
    [token]
  );

  const openConversation = useCallback(
    async (id) => {
      if (!id) {
        setDetailError("No conversation ID is linked to this record.");
        setActive("conversation-detail");
        return;
      }

      setSelectedConversation(id);
      setActive("conversation-detail");
      setDetailLoading(true);
      setDetailError("");
      setConversationData(null);

      try {
        setConversationData(
          await request(
            `/api/admin/dashboard/conversations/${id}`,
            { token }
          )
        );
      } catch (err) {
        setDetailError(
          err.message || "Unable to load conversation transcript."
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [token]
  );

  const reloadDetail = useCallback(() => {
    if (active === "taxpayer-detail" && selectedTaxpayer) {
      openTaxpayer(selectedTaxpayer);
    } else if (active === "conversation-detail" && selectedConversation) {
      openConversation(selectedConversation);
    }
  }, [
    active,
    selectedTaxpayer,
    selectedConversation,
    openTaxpayer,
    openConversation,
  ]);

  const backFromDetail = useCallback(() => {
    if (active === "conversation-detail" && selectedTaxpayer) {
      openTaxpayer(selectedTaxpayer);
      return;
    }

    navigate(active === "taxpayer-detail" ? "individuals" : "assessments");
  }, [active, selectedTaxpayer, openTaxpayer, navigate]);

  const activeTitle = useMemo(
    () =>
      ({
        overview: "Overview",
        individuals: "Individuals",
        employers: "Companies / Employers",
        "business-register": "Business Register",
        assessments: "Assessments",
      })[active] || "Details",
    [active]
  );

  function login(tokenValue, email) {
    sessionStorage.setItem(TOKEN_KEY, tokenValue);
    setAdmin({ email });
    setToken(tokenValue);
    setActive("overview");
    setRefreshKey((value) => value + 1);
  }

  if (!token) return <Login onLogin={login} />;

  const navItems = [
    { id: "overview", text: "Overview", icon: "overview" },
    { id: "individuals", text: "Individuals", icon: "people" },
    { id: "employers", text: "Companies / Employers", icon: "company" },
    { id: "assessments", text: "Assessments", icon: "receipt" },
    { id: "business-register", text: "Business Register", icon: "company" },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-symbol">E</span>
          <span>
            <strong>EIRS</strong>
            <small>ADMINISTRATION</small>
          </span>
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>

        <nav className="main-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${
                active === item.id ||
                (item.id === "individuals" &&
                  active === "taxpayer-detail") ||
                (item.id === "assessments" &&
                  active === "conversation-detail")
                  ? "active"
                  : ""
              }`}
              onClick={() => navigate(item.id)}
            >
              <Icon name={item.icon} />
              <span>{item.text}</span>
              {item.id === "overview" && <span className="nav-dot" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-help">
            <div className="help-mark">i</div>
            <div>
              <strong>Need help?</strong>
              <small>Contact your system administrator.</small>
            </div>
          </div>

          <button className="nav-item logout-item" onClick={logout}>
            <Icon name="logout" />
            <span>Sign out</span>
          </button>

          <div className="sidebar-version">
            EIRS Taxpayer System <span>Admin portal</span>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Admin portal</span>
            <span className="crumb-separator">/</span>
            <strong>{activeTitle}</strong>
          </div>

          <div className="topbar-right">
            <span className="system-status">
              <span /> API connected
            </span>
            <div className="admin-chip">
              <span className="admin-avatar">
                {(admin?.full_name || admin?.email || "A")
                  .slice(0, 1)
                  .toUpperCase()}
              </span>
              <span>
                <strong>
                  {admin?.full_name || admin?.email || "Administrator"}
                </strong>
                <small>Administrator</small>
              </span>
            </div>
          </div>
        </header>

        <div className="page-content">
          {active === "overview" && (
            <Overview
              data={overview}
              loading={loading}
              error={error}
              onRetry={() => setRefreshKey((value) => value + 1)}
              onNavigate={navigate}
            />
          )}

          {active === "individuals" && (
            <Individuals
              data={individuals}
              loading={loading}
              error={error}
              search={search}
              setSearch={setSearch}
              onRetry={() => setRefreshKey((value) => value + 1)}
              onOpen={openTaxpayer}
            />
          )}

          {active === "employers" && (
            <Employers
              data={employers}
              loading={loading}
              error={error}
              search={search}
              setSearch={setSearch}
              onRetry={() => setRefreshKey((value) => value + 1)}
              onOpenConversation={openConversation}
            />
          )}

          {active === "assessments" && (
            <Assessments
              data={assessments}
              loading={loading}
              error={error}
              search={search}
              setSearch={setSearch}
              onRetry={() => setRefreshKey((value) => value + 1)}
              onOpenTaxpayer={openTaxpayer}
              onOpenConversation={openConversation}
              filingFilter={filingFilter}
              setFilingFilter={setFilingFilter}
            />
          )}

          {active === "taxpayer-detail" && (
            <TaxpayerDetail
              data={taxpayerData}
              loading={detailLoading}
              error={detailError}
              onBack={backFromDetail}
              onOpenConversation={openConversation}
              onRetry={reloadDetail}
            />
          )}

          {active === "conversation-detail" && (
            <ConversationDetail
              data={conversationData}
              loading={detailLoading}
              error={detailError}
              onBack={backFromDetail}
              onRetry={reloadDetail}
            />
          )}

          {active === "business-register" && (
            <BusinessRegister token={token} />
          )}
        </div>

        <footer className="main-footer">
          <span>
            © {new Date().getFullYear()} Edo State Internal Revenue Service
          </span>
          <span>Taxpayer information · Authorized use only</span>
        </footer>
      </main>
    </div>
  );
}
