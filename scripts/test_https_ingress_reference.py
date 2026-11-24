"""Offline + Docker syntax checks for the opt-in loopback HTTPS ingress example.

No deployment, credentials, DNS registration or externally reachable port.
Docker/OpenSSL validation is intended for the Ubuntu CI runner.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "deploy" / "ingress" / "evidenceos.conf.template"
OVERLAY = ROOT / "compose.https-ingress-reference.yaml"
HOST_VAR = "${EVIDENCEOS_INGRESS_HOST}"
UPSTREAM_VAR = "${EVIDENCEOS_INGRESS_UPSTREAM}"


def render_for_syntax_check(text: str) -> str:
    """Use harmless, explicit test placeholders: never real hostnames or keys."""
    if text.count(HOST_VAR) < 3 or text.count(UPSTREAM_VAR) != 2:
        raise ValueError("Unexpected ingress template shape")
    rendered = text.replace(HOST_VAR, "research.example.invalid")
    rendered = rendered.replace(UPSTREAM_VAR, "127.0.0.1:9000")
    if "${EVIDENCEOS_INGRESS_" in rendered:
        raise ValueError("Unexpected unexpanded ingress variable")
    return rendered


class IngressReferenceTests(unittest.TestCase):
    def test_host_is_pinned_and_unknown_hosts_are_rejected(self) -> None:
        content = render_for_syntax_check(TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("listen 8080 default_server;", content)
        self.assertIn("return 444;", content)
        self.assertIn("listen 8443 ssl default_server;", content)
        self.assertIn("return 421;", content)
        self.assertIn("return 308 https://research.example.invalid$request_uri;", content)
        self.assertIn("proxy_set_header Host research.example.invalid;", content)
        self.assertNotIn("return 308 https://$host", content)

    def test_tls_forwarding_and_abuse_limits(self) -> None:
        content = render_for_syntax_check(TEMPLATE.read_text(encoding="utf-8"))
        for line in (
            "ssl_protocols TLSv1.2 TLSv1.3;",
            "client_max_body_size 10m;",
            "proxy_set_header X-Forwarded-Proto https;",
            "proxy_set_header X-Forwarded-For $remote_addr;",
            "proxy_hide_header Strict-Transport-Security;",
            'add_header Strict-Transport-Security "max-age=31536000" always;',
            "limit_req zone=ingress_global burst=40 nodelay;",
            "limit_req zone=ingress_login burst=4 nodelay;",
            "proxy_pass http://127.0.0.1:9000;",
        ):
            self.assertIn(line, content)
        self.assertNotIn("$proxy_add_x_forwarded_for", content)
        # Do not overwrite the application's nonce-based CSP header.
        self.assertNotIn("add_header Content-Security-Policy", content)
        self.assertIn("access_log /dev/stdout evidenceos_safe;", content)
        self.assertNotIn("$request_uri", content.split("log_format evidenceos_safe")[1].split(";")[0])

    def test_overlay_never_opens_a_public_host_port(self) -> None:
        content = OVERLAY.read_text(encoding="utf-8")
        self.assertIn('"127.0.0.1:', content)
        self.assertIn("NGINX_ENVSUBST_FILTER:", content)
        self.assertIn('EVIDENCEOS_INGRESS_HOST: ${EVIDENCEOS_INGRESS_HOST:?', content)
        self.assertIn("./deploy/ingress/certs/privkey.pem", content)
        self.assertNotIn("0.0.0.0:", content.replace("127.0.0.1:", ""))
        self.assertIn("no-new-privileges:true", content)

    @unittest.skipUnless(
        sys.platform.startswith("linux") and shutil.which("docker") and shutil.which("openssl"),
        "Docker/OpenSSL syntax validation runs on Linux CI",
    )
    def test_real_nginx_parser_rejects_no_directives(self) -> None:
        with tempfile.TemporaryDirectory(prefix="evidenceos-ingress-check-") as folder:
            root = Path(folder)
            config = root / "default.conf"
            cert = root / "fullchain.pem"
            key = root / "privkey.pem"
            content = render_for_syntax_check(TEMPLATE.read_text(encoding="utf-8"))
            config.write_text(content, encoding="utf-8")
            subprocess.run(
                [
                    "openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", str(key), "-out", str(cert),
                    "-days", "1", "-nodes", "-subj", "/CN=research.example.invalid",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            # Docker socket exists only in CI; the container has no network
            # and is never published, started as a server, or given credentials.
            result = subprocess.run(
                [
                    "docker", "run", "--rm", "--network", "none",
                    "-v", f"{config}:/etc/nginx/conf.d/default.conf:ro",
                    "-v", f"{cert}:/etc/nginx/ingress-tls/fullchain.pem:ro",
                    "-v", f"{key}:/etc/nginx/ingress-tls/privkey.pem:ro",
                    "nginx:stable-alpine", "nginx", "-t",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
