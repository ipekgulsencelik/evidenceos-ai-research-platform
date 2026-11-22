"""No-network tests for the disposable OIDC staging generator and isolation."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_oidc_staging as generator


ROOT = Path(__file__).resolve().parent.parent


class IsolatedOidcStagingTests(unittest.TestCase):
    def test_generated_realm_is_confidential_and_api_audience_is_distinct(self):
        realm = generator.realm_config("client-test-secret", "owner-test-secret", "member-test-secret")
        self.assertEqual(realm["realm"], "evidenceos-staging")
        self.assertEqual(realm["sslRequired"], "external")
        self.assertEqual(len(realm["users"]), 2)
        self.assertEqual({u["username"] for u in realm["users"]}, {"e2e-owner", "e2e-member"})
        self.assertEqual(
            {u["credentials"][0]["value"] for u in realm["users"]},
            {"owner-test-secret", "member-test-secret"},
        )
        self.assertTrue(all(not u["credentials"][0]["temporary"] for u in realm["users"]))
        clients = {c["clientId"]: c for c in realm["clients"]}
        self.assertIn("evidenceos-web-staging", clients)
        self.assertIn("evidenceos-api-staging", clients)
        web = clients["evidenceos-web-staging"]
        self.assertFalse(web["publicClient"])
        self.assertFalse(web["directAccessGrantsEnabled"])
        self.assertEqual(web["secret"], "client-test-secret")
        self.assertEqual(web["redirectUris"], ["http://127.0.0.1:3101/auth/callback"])
        self.assertEqual(
            web["protocolMappers"][0]["config"]["included.custom.audience"],
            "evidenceos-api-staging",
        )
        self.assertEqual(
            web["protocolMappers"][0]["config"]["id.token.claim"], "false"
        )

    def test_staging_compose_is_namespaced_without_local_db_or_external_db_redis(self):
        config = (ROOT / "compose.oidc-staging.yaml").read_text(encoding="utf-8")
        self.assertIn("name: evidenceos-oidc-staging", config)
        self.assertIn("staging_postgres_data:", config)
        self.assertIn("127.0.0.1:3101:3000", config)
        self.assertIn("127.0.0.1:8101:8000", config)
        self.assertIn("127.0.0.1:8443:8443", config)
        self.assertIn("EVIDENCEOS_SECURITY_MODE: oidc", config)
        self.assertIn("EVIDENCEOS_APP_ENV: test", config)
        self.assertIn("quay.io/keycloak/keycloak:26.8.2", config)
        # Keycloak's import checks the filename against the realm name.
        # Retain the existing *host* source so previously generated secrets
        # and TLS files remain valid after a simple git pull/recreate.
        expected_import_name = generator.realm_config("s", "a", "b")["realm"] + "-realm.json"
        self.assertIn(
            "./staging/runtime/evidenceos-realm.json:/opt/keycloak/data/import/"
            + expected_import_name + ":ro",
            config,
        )
        self.assertNotIn(
            "/opt/keycloak/data/import/evidenceos-realm.json:ro",
            config,
        )
        self.assertNotIn("postgres_data:", config.replace("staging_postgres_data:", ""))
        self.assertNotIn("0.0.0.0:", config)

    def test_existing_secret_file_refuses_overwrite_without_touching_it(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / ".env.oidc-staging"
            env.write_text("preserve-local-test-secret", encoding="utf-8")
            with (
                patch.object(generator, "ENV_FILE", env),
                patch.object(generator, "RUNTIME", Path(directory) / "nonexistent"),
            ):
                self.assertEqual(generator.main(), 1)
            self.assertEqual(env.read_text(encoding="utf-8"), "preserve-local-test-secret")

    def test_local_primary_compose_and_dotenv_are_not_modified_by_generator(self):
        script = (ROOT / "scripts" / "prepare_oidc_staging.py").read_text(encoding="utf-8")
        self.assertNotIn('ROOT / ".env"', script)
        self.assertNotIn('ROOT / "compose.yaml"', script)
        self.assertIn('ROOT / ".env.oidc-staging"', script)
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("staging/runtime/", ignored)


if __name__ == "__main__":
    unittest.main()
