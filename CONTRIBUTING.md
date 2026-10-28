# Contributing

Use synthetic/releasable fixtures, never customer audio or scripts. Describe the trigger, observed behavior, expected result and relevant tests. Do not paste API keys, private paths or raw provider payloads into issues.

Run Python and JavaScript regressions before proposing changes. Test fixed header controls, drawer keyboard focus, saving conflicts, sound-only changes, exports and nonzero offsets in a browser. A patch must preserve current review data and must not silently weaken fidelity or delivery gates.

New provider integrations use local credentials, configurable endpoints/models and explicit request accounting. Software tests are offline and must not make billed AI requests. Changes are MIT licensed; include notices for any separately licensed dependency or asset.
