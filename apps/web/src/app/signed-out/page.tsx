/** Public return from a completed RP-Initiated Logout.
 * Never begin a new OIDC authorization flow automatically here.
 */
export const dynamic = "force-dynamic";

export default function SignedOutPage() {
  return (
    <main style={{
      maxWidth: 460, margin: "12vh auto", padding: 32,
      fontFamily: "system-ui, sans-serif", lineHeight: 1.6,
      textAlign: "center",
    }}>
      <h1>You are logged out</h1>
      <p>Your EvidenceOS session has ended.</p>
      <a href="/signin" style={{
        display: "inline-block", padding: "12px 20px", borderRadius: 8,
        background: "#147d79", color: "#fff", textDecoration: "none",
        fontWeight: 600, marginTop: 12,
      }}>Sign in again</a>
      <p style={{ marginTop: 28, fontSize: 13, color: "#52646f" }}>
        EvidenceOS Research Intelligence
      </p>
    </main>
  );
}
