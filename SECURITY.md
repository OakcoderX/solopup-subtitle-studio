# Local service and credential security

This is a single-user local workbench, bound to 127.0.0.1 by default. It has no multi-user authentication; do not expose it directly to a LAN or the internet. Keep the service running only for trusted local work. Origin checks and revision tokens do not replace authentication or a full remote-service security review.

Recipients configure Qwen using configure_qwen.command or scripts/configure_qwen.py. Input is hidden; the local key is stored with owner-only permissions and excluded from Git/archives. Configure the correct HTTPS endpoint and account-supported models. Environment variables override local settings. Configuration alone makes no API request. Never paste a key into chat, issues, command arguments or logs.

Two packages exist: an internal portable system package (may contain private project knowledge) and a public-source export (excludes private projects, actual episode fixtures and third-party manuals). Both exclude keys and runtime data. The public builder exports a clean snapshot; it does not certify the parent production repository history as safe. Old private archives must not be published.

For a suspected vulnerability, provide a minimal synthetic reproduction privately to the repository owner. Do not disclose customer media, keys, private paths or provider response payloads in a public issue. Revoke any exposed credential at its provider.

## v1.9 boundary hardening

GET/HEAD/POST validate one Host against loopback hostnames and the actual port. Supplied Origin must be a trusted local origin; cross-site Fetch Metadata is rejected. Provider writes additionally require a per-process configuration token, JSON and bounded request size; provider status is non-cacheable and never returns a key. Runtime provider endpoints are HTTPS-validated even when supplied through environment variables. Configuration stores a local plaintext key with owner-only permissions, not an OS keychain. Environment values override local configuration.

A focused Standard source audit covered the service, provider and package boundaries; one conditional DNS-rebinding issue in v1.8 was repaired and regression-tested in v1.9. This does not certify complete frontend/repair/dependency or Windows ACL security. No actual project media or paid provider calls were used in security testing.
