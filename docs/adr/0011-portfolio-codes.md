# Open a Portfolio on another device with a Portfolio Code

## Decision — 2026-11-07

Every Portfolio has a Portfolio Code: a number that is unique across the service. New codes use 4 digits while that space has room, then 5, then 6. The owner chose short codes so a Portfolio opens on another device without signing in.

A browser with no access first sees one screen that asks for the code. Google sign-in and a new Portfolio are smaller options on the same screen.

A correct code issues a Portfolio Pass: an opaque browser cookie, stored only as a hash, that gives full read and write access to that one Portfolio. A pass cannot list or reach other Portfolios in the Workspace, manage codes, create Portfolios, or use User-only features. While a pass cookie is present, it wins over the browser's User or Guest cookie. Closing the Portfolio on that device removes the pass and restores the browser's own access.

The owner, as a User or Guest of the Workspace, can replace the code. Replacement revokes every pass for that Portfolio. A pass expires after 90 days without use. Using a pass keeps a Guest Workspace from expiring.

## Accepted risk

A short code can be guessed, and the chance grows with the number of Portfolios. The owner accepted this for the beta's small user base. The service limits failed attempts per client and across the whole service, and it never says which Portfolio a code belongs to.

## Relationship to earlier decisions

This adds a third way to reach Portfolio data next to Google sign-in ([ADR 0004](0004-google-primary-with-email-magic-link.md)) and Guest cookies ([ADR 0009](0009-cookie-only-guest-workspaces.md)). It does not add teams or shared Workspaces; a code opens one Portfolio for whoever holds it.
