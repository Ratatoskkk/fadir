# Host the open beta on an Ubuntu Server Hyper-V VM

## Current beta decision — 2026-09-05

The open beta will run on a dedicated Ubuntu Server LTS VM under Hyper-V instead of a rented VPS. Cloudflare Tunnel will provide public access for `ratatosk.dev`.

The beta will not use off-site backups. It has no one-hour data-loss target and no four-hour restore guarantee.

Release readiness still requires proof of service restart, release rollback, and service reconstruction. These proofs do not recover lost Portfolio data.

## Decision history

The original decision used current hardware and assigned power, network isolation, stable public access, and backup duties to the owner. The current beta decision supersedes its off-site backup and recovery targets.
