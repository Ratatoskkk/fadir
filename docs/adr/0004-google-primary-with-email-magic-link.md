# Use Google-only sign-in for the beta

## Current beta decision — 2026-09-05

The beta accepts Google sign-in only. Email magic-link recovery is deferred. The beta will not use an email sender service or an email sign-in flow.

Google identity uses the provider issuer and subject, not the email address, as the durable key. A User Session expires after 30 days without activity, and the User can view and revoke active sessions.

## Decision history

The earlier decision planned Google as the primary sign-in method and an email magic link as recovery. It allowed a User to attach both verified Login Identities. It used the provider subject, not the email address, as the durable Google key.

The earlier decision considered a free external transactional email service. Resend was the first candidate, and Brevo was the fallback. The application would keep the email service behind a small interface.

The VM will not operate an email server while the later email-recovery scope remains deferred. This history does not add email recovery to the beta.
