# RB-13-origin-fallback: Origin-direct fallback (Cloudflare outage)

## Trigger
Cloudflare DNS/Tunnel/Pages unavailable (NET-07).

## Owner
IC

## Steps
1. Pre-staged (before event): firewall rule allowing direct 443 to the VM; public-trusted
   certificate installed (Origin CA alone is NOT browser-trusted).
2. Flip DNS-only record at the registrar (low TTL pre-set).
3. Serve the frontend from origin (the image runs the SPA locally).
4. Announce to participants from the status page (off-host — independently reachable).

## Verification
- app + api reachable directly; no mixed-content errors.
- Status page showed the incident the whole time.

## Rollback
Flip DNS back to proxied once Cloudflare recovers.

