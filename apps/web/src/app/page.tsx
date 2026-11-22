import { ResearchWorkspace } from "@/components/research-workspace";

// Evaluate OIDC mode at request time: Docker sets it when the container starts.
export const dynamic = "force-dynamic";

export default function HomePage() {
  return (
    <>
      {process.env.EVIDENCEOS_SECURITY_MODE === "oidc" && (
        <header style={{
          display: "flex", justifyContent: "flex-end", alignItems: "center",
          gap: 12, padding: "8px 16px", background: "#14283e", color: "#fff",
        }}>
          <span style={{ fontSize: 12 }}>Authenticated research session</span>
          <form action="/auth/logout" method="POST">
            <button type="submit" style={{
              padding: "5px 12px", border: "1px solid #a3b5c5",
              borderRadius: 6, background: "transparent", color: "#fff", cursor: "pointer",
            }}>Sign out</button>
          </form>
        </header>
      )}
      <ResearchWorkspace />
    </>
  );
}
