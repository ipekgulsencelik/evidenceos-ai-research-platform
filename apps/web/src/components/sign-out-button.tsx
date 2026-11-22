"use client";

import { useState } from "react";

import { LOGOUT_REQUEST_HEADER } from "@/lib/logout-request";

/** Same-origin fetch explicitly carries a CSRF-resistant, custom header.
 * A normal HTML form navigation can omit Origin in some browser contexts.
 */
export function SignOutButton() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signOut(): Promise<void> {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      const response = await fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: { [LOGOUT_REQUEST_HEADER]: "1" },
      });
      // Follow the server's 303, but do not claim success if revocation
      // failed or the expected sign-in redirect did not happen.
      if (!response.ok || !response.redirected ||
          new URL(response.url).origin !== window.location.origin ||
          new URL(response.url).pathname !== "/signin") {
        throw new Error("Unable to confirm browser session revocation.");
      }
      window.location.replace("/signin");
    } catch {
      setError("Sign out could not be confirmed. Please try again.");
      setPending(false);
    }
  }

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <button type="button" onClick={() => { void signOut(); }} disabled={pending}
        style={{
          padding: "5px 12px", border: "1px solid #a3b5c5",
          borderRadius: 6, background: "transparent", color: "#fff",
          cursor: pending ? "wait" : "pointer",
        }}>
        {pending ? "Signing out…" : "Sign out"}
      </button>
      {error && <span role="alert" style={{ fontSize: 12 }}>{error}</span>}
    </div>
  );
}
