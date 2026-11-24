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
      // The same-origin server must confirm Redis revocation and provide
      // the trusted next navigation target. A browser fetch must never
      // follow a cross-origin IdP redirect; that would be blocked by CORS.
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok || !payload || typeof payload !== "object" ||
          !("next" in payload) || typeof payload.next !== "string") {
        throw new Error("Unable to confirm browser session revocation.");
      }
      const next: string = payload.next;
      if (next === "/signin" || next === "/signin?notice=provider-logout-unavailable") {
        window.location.replace(next);
      } else {
        const url = new URL(next);
        if (url.protocol !== "https:" || url.username || url.password ||
            url.hash || !url.pathname.endsWith("/protocol/openid-connect/logout")) {
          throw new Error("Unexpected provider logout destination.");
        }
        // This is a navigation (not a fetch) so Keycloak can clear SSO cookies.
        window.location.assign(url.href);
      }
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
