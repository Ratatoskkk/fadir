# Use Google first with email magic-link recovery

faðir will use Google as the primary sign-in method and an email magic link as recovery. A User can attach both verified Login Identities. The service will use the provider subject, not the email address, as the durable Google key.

The beta will use a free external transactional email service. Resend is the first candidate, and Brevo is the fallback. The application will keep the email service behind a small interface.

The VM will not operate an email server while a suitable free service exists. This choice protects email delivery quality and reduces VM maintenance.
