# Use Cloudflare Tunnel for public ingress

Public traffic will reach the owner-managed VM through Cloudflare Tunnel instead of an inbound router port. This choice hides the origin address and avoids a public home-network port. It makes Cloudflare part of the service trust and availability boundary.

The beta will use quiet Guest abuse controls. Cloudflare controls, server rate limits, request size limits, and Guest quotas will protect the service. Turnstile will remain available if abuse appears.
