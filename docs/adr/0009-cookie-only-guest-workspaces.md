# Use cookie-only Guest Workspaces

A Guest Workspace will use one opaque browser cookie. The service will store only a secure hash of the Guest secret.

The service will not use a MAC address or a device identifier. A Guest loses access when the cookie is lost.

The service will delete a Guest Workspace after 90 days without access. It will show a quiet warning after the first saved Portfolio data.

When a Guest signs in, the service will offer explicit Claim, Portfolio Transfer, or Portfolio Merge choices. It will not combine private data without confirmation.
