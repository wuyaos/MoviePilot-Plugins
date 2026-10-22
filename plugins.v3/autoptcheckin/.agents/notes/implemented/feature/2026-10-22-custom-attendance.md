# Agent Note: Custom attendance transport

Status: implemented

## Problem
Custom verification proves page reachability, not attendance. Custom entries have no per-site verified declaration, so inheriting native calibration gates prevents an explicitly selected custom action from running.

## Decision
Configured, enabled and sign-selected custom entries use the existing NexusSignin form discovery and message chain. Selection authorizes execution without changing native verified gates; unlock_all_sites never replaces action selection. An absent unique same-origin attendance POST form yields custom_signin_pending, not a guessed protocol. The local custom Cookie remains the credential source, avoiding an unrelated native credential-resolution expansion.

Emulated sites use Browserless page navigation for both reads and the existing HTTP client for a single POST. Cookie values are synchronized within the execution only. The browser context is isolated and released with the connection. Disabled Browserless never falls back to HTTP-only execution. Read-only verify retains its login evidence semantics.

## Alternatives considered
Full browser form submission preserves browser identity across all requests, but requires additional navigation and JavaScript-submit handling. The authorized hybrid option reuses the existing submission/readback discipline, at the cost of not supporting sites that bind POSTs to browser transport fingerprints. Such sites remain unconfirmed, never retried automatically.

Keeping all custom sites pending avoids protocol assumptions but fails the requested standard NexusPHP use case. Dedicated non-Nexus protocols and captcha handling remain outside this change.

## Consequences
Offline consumer tests cover success/already/unconfirmed, gates, numeric IDs, submit exceptions, fresh reads and hybrid Cookie synchronization. No real site or Browserless server is contacted. Browserless/Playwright availability and transport-fingerprint compatibility require separately authorized runtime verification.

Existing root native-dual-track note overlaps only on the general native/custom split and is retained unchanged by this slice; root proposed/rejected directories are absent. This note stays under the plugin because this task explicitly restricts writable paths.
