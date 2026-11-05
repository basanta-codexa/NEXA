import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="landing">
      <nav className="nav-landing">
        <Link className="landing-brand" href="/">
          <div className="brand-mark">N</div>
          <div className="landing-brand-name">NEXA</div>
        </Link>
        <div style={{ display: "flex", gap: 10 }}>
          <Link className="btn btn-ghost" href="/login">Sign in</Link>
          <Link className="btn btn-primary" href="/signup">Create workspace</Link>
        </div>
      </nav>

      {/* Editorial hero */}
      <header className="hero">
        <div>
          <div className="hero-eyebrow">Multi-tenant AI workforce</div>
          <h1>
            The agent platform <em>your company</em> can actually stake its name on.
          </h1>
          <p className="hero-sub">
            NEXA gives every team production agents — grounded in your tenant&apos;s
            own knowledge, bounded by real tool permissions, and isolated by design.
            No shared data, no shared risk, no prototype apologies.
          </p>
          <div className="hero-ctas">
            <Link className="btn btn-primary" href="/signup">Create your workspace →</Link>
            <Link className="btn" href="/login">Sign in to console</Link>
          </div>
          <p className="hero-proof">
            Isolated tenants · Database-backed RBAC · RAG with citations ·
            LiveKit voice pipeline · Invite-only onboarding
          </p>
        </div>

        {/* Evidence panel instead of marketing bullets */}
        <div className="transcript" aria-hidden="true">
          <div className="transcript-bar"><span className="dot" /><span className="dot" /><span className="dot" /></div>
          <div className="t-user">Customer: Where is my refund for order #101?</div>
          <div className="t-tool">↳ lookup_order(101) → Shipped · Arrives Nov 7</div>
          <div className="t-tool">↳ search_knowledge("refund policy") → 1 cited chunk</div>
          <div className="t-agent">Agent: Your order shipped and arrives Nov 7. Per our policy, refunds are
            issued within 5 business days of delivery. Want me to start it?</div>
          <div className="t-citation">Source: Refund Policy · chunk 3</div>
        </div>
      </header>

      {/* Value strip */}
      <section className="value-strip">
        <div className="value">
          <h3>Isolated by default</h3>
          <p>Every tenant gets its own agents, knowledge, users and roles. No cross-tenant leakage — enforced in the database.</p>
        </div>
        <div className="value">
          <h3>Grounded, not guessed</h3>
          <p>Agents answer from your documents with citations. If the knowledge isn&apos;t there, the agent says so — it doesn&apos;t invent.</p>
        </div>
        <div className="value">
          <h3>Voice-native</h3>
          <p>LiveKit-powered realtime voice: STT → agent → TTS, with barge-in and per-tenant session isolation.</p>
        </div>
      </section>

      <footer className="footer-landing">
        <span>NEXA — AI workforce infrastructure</span>
        <span>Invite-only · Multi-tenant · Self-hosted</span>
      </footer>
    </div>
  );
}
