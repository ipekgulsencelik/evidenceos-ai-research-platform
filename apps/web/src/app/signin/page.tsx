/** Public entry for provider-configured login (no credentials handled here). */
export const dynamic = "force-dynamic";

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ notice?: string }>;
}) {
  const ready = process.env.EVIDENCEOS_SECURITY_MODE === "oidc";
  const { notice } = await searchParams;
  return (
    <main style={{
      maxWidth: 480, margin: "12vh auto", padding: 32,
      fontFamily: "system-ui, sans-serif", lineHeight: 1.6,
    }}>
      <h1>EvidenceOS</h1>
      <p>Sign in with your organization’s identity provider to access your research workspace.</p>
      {notice === "provider-logout-unavailable" && (
        <p role="alert">
          Your EvidenceOS browser session has ended, but identity provider sign-out
          could not be started. Your organization SSO session may still be active.
        </p>
      )}
      {ready ? (
        <a href="/auth/login" style={{
          display: "inline-block", padding: "10px 18px", borderRadius: 8,
          background: "#243b53", color: "white", textDecoration: "none",
        }}>Sign in securely</a>
      ) : (
        <p>Organization sign-in is not enabled.</p>
      )}
      <p style={{ fontSize: 13 }}>
        Your access is restricted to research projects where you are a member.
      </p>
    </main>
  );
}
