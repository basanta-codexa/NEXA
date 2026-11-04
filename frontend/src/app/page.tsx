import Link from "next/link";

const FEATURES = [
  {
    icon: "◎",
    title: "AI agents that reason",
    body: "Build agents with system prompts, provider-agnostic LLMs (OpenAI, Groq, Ollama, xAI) and a bounded tool-calling loop.",
  },
  {
    icon: "▤",
    title: "Knowledge that grounds them",
    body: "Upload documents and retrieve verified, cited chunks before every answer. Grounded in your tenant's data only.",
  },
  {
    icon: "🔒",
    title: "True multi-tenancy",
    body: "Row-level tenant isolation, database-backed roles and granular permissions — admins, members and read-only roles.",
  },
  {
    icon: "🎙",
    title: "Voice-ready",
    body: "A LiveKit-powered voice pipeline (STT → agent → TTS) for realtime conversations with every agent you ship.",
  },
];

export default function LandingPage() {
  return (
    <div className="landing">
      {/* Top navigation */}
      <nav className="nav-landing">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="brand-mark">N</div>
          <div className="brand-name">NEXA</div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <Link className="btn btn-ghost" href="/login">
            Sign in
          </Link>
          <Link className="btn btn-primary" href="/signup">
            Get invite →
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <header className="hero">
        <div className="hero-eyebrow">● Multi-tenant AI workforce platform</div>
        <h1>
          Ship <span>AI agents</span>
          <br />
          your company trusts.
        </h1>
        <p className="hero-sub">
          NEXA is the control plane for tenant-isolated AI agents — with tool
          calling, memory, RAG-grounded knowledge, granular roles and a
          production voice pipeline. One backend. Every team. Full auditability.
        </p>
        <div className="hero-ctas">
          <Link className="btn btn-primary" href="/signup">
            Create your workspace
          </Link>
          <Link className="btn" href="/login">
            Sign in to console
          </Link>
        </div>
      </header>

      {/* Feature grid */}
      <section className="features">
        {FEATURES.map((f) => (
          <div className="feature" key={f.title}>
            <div className="feature-icon">{f.icon}</div>
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </div>
        ))}
      </section>

      <footer className="footer-landing">
        NEXA — AI workforce infrastructure · Built for multi-tenant SaaS ·
        Invite-only access
      </footer>
    </div>
  );
}
