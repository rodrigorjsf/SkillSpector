---
paths:
  - "src/skillspector/input_handler.py"
---

# Ingest boundary

Everything a Scan reads enters through `InputHandler.resolve()`, the only SSRF gate in the codebase.
Treat every change here as security-relevant, not as plumbing.

- **Two allowlists, deliberately different.** `ALLOWED_DOWNLOAD_HOSTS` is `ALLOWED_GIT_HOSTS` plus
  `raw.githubusercontent.com` and `huggingface.co`. Adding a host to the wrong one widens the wrong
  surface — a git clone runs a remote's hooks and filters, a download does not.
- **Two matching semantics, also deliberate.** `_is_git_url` tests `allowed in host` (substring) to
  *route* clone-vs-download; `_validate_url_host` is the *gate* and tests
  `host == allowed or host.endswith("." + allowed)`. The substring form looks like the classic
  allowlist bug and is not one — tightening it changes routing, and loosening the gate to match it
  opens `github.com.attacker.tld`.
- `resolve()` only dispatches; `_clone_git` and `_download_file` each call `_validate_url_host`
  themselves. A new ingest path that forgets the call inherits no SSRF protection at all.
- `_is_private_ip` runs after the allowlist and does a live `socket.getaddrinfo` lookup for
  non-literal hosts, rejecting if **any** resolved address is private. It fails closed — a
  `gaierror`/`OSError` returns `True`. Real network I/O, so a test on this path must patch it.
- The byte cap is enforced **twice** on download: against the declared `Content-Length`, then
  against the running total while streaming. Dropping the second trusts a lying server.
- `INGEST_MAX_BYTES` (100 MiB) sits *above* the per-file analysis cap on purpose, so a legitimate
  multi-file skill is not blocked at ingest. That cap is `MAX_FILE_CHARS` in
  `nodes/analyzers/static_runner.py`, and it counts **characters** of decoded text where every
  ingest cap counts bytes on disk — the two are only comparable once you assume an encoding, so
  restating one in the other's unit is how the comment beside `INGEST_MAX_BYTES` went wrong before.
  `INGEST_MAX_ZIP_MEMBERS` (10 000) is a separate axis, bounding the many-tiny-files zip bomb
  the byte cap alone cannot.
- `IngestLimitExceededError` subclasses `ValueError` so callers already catching `ValueError` from
  `resolve()` keep working — do not change the base class. The zip-slip guard raises a plain
  `ValueError`, so `except IngestLimitExceededError` does **not** catch it.
- Coverage: `tests/unit/test_input_handler{,_bounds,_ssrf}.py`. A change to any limit, allowlist or
  guard belongs in one of them.
