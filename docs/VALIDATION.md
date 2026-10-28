# Candidate validation

SoloPup Subtitle Studio 2.0.0-rc.5 · 2026-10-28 · local public-preview preparation.

| Check | Verified result |
| --- | --- |
| Clean extracted source | 259 Python tests passed; 4 JavaScript tests passed |
| Offline end-to-end | Synthetic video and two imported SRTs passed the actual background queue, saved review, stale-save rejection, per-language ITT/SRT export and project export |
| iTT | Exported synthetic files also checked against a separately held authorized schema; that schema is not distributed |
| Reference viewer | Original language-summary pages load; missing-media state loads and is explicit; navigation omits unavailable source documents |
| Public interface | Product branding and dual-track editor inspected using synthetic data |
| Qwen onboarding | First-use reminder and settings entry inspected; setup guide loads; cloud jobs without a Key rejected before insertion; paired-SRT offline review succeeds; no model calls made |
| Provider guidance | Trial-quota and API-Key guidance checked against Alibaba Cloud official documentation on 2026-10-28; account, region and exact-model eligibility must be checked by each user |
| Isolation | No private productions/characters, actual episode fixtures, original manuals/schemas, media, databases, keys or private Git history included |
| Original user work | 2189 production state/history files unchanged in the maintainer workspace |
| Paid AI and publication | Zero paid calls in software validation; publication and remote CI status are reported separately on GitHub |

The public edition intentionally excludes private-project orchestration and its tests. Generic functionality is verified in the public snapshot itself; internal-only test counts are not used as a public-edition acceptance claim. Original source text and source/translation review remain distinct from same-language lexical-fidelity rules.

Remote CI has not run: the publishing credential lacks workflow permissions. A workflow template is supplied under `docs/ci/`.

Environment: local macOS, Python3.9.6, Node.js and FFmpeg. Fresh-machine setup, Windows/Linux manual acceptance, actual provider/account access, full audiovisual language quality and platform receiving/accepting an episode remain unverified here. A test result is not a certification.
