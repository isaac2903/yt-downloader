# Cloudflare Tunnel migration for n8n

## Objective

Serve the existing Raspberry Pi n8n instance at `https://n8n.fewshotsolutions.co` without depending on the home's dynamic public IP or inbound router port forwarding. Preserve the main website, Google Workspace email authentication, and the Calendly redirect throughout the DNS migration.

## Selected approach

Move authoritative DNS for `fewshotsolutions.co` from Namecheap BasicDNS to Cloudflare's free plan, then publish n8n through a named Cloudflare Tunnel running on the Raspberry Pi. The domain remains registered and billed at Namecheap.

The alternatives were rejected for this deployment:

- Namecheap Dynamic DNS would retain public-IP exposure, Caddy, and inbound router ports.
- Tailscale Funnel would require a `*.ts.net` hostname instead of the business domain.

## Existing services and DNS that must be preserved

- Apex website: `A @ 185.158.133.1`
- Website alias: `A www 185.158.133.1`
- n8n during migration: `A n8n 49.245.39.19`
- Google Workspace mail: `MX @ smtp.google.com`, priority `1`
- SPF: `TXT @ v=spf1 include:_spf.google.com ~all`
- Google verification: `TXT @ google-site-verification=SaJLghOUWswqbrrBgTrAIv9_EccGGvTV8h1d82FSwC0`
- Google verification: `TXT @ google-site-verification=xLkNTpTuPKgsz_c3LasmOrXFZwGGiDwnpmwQAaVvAH0`
- DMARC: `TXT _dmarc v=DMARC1; p=quarantine; rua=mailto:dmarc@fewshotsolutions.co; fo=1; pct=20`
- Google DKIM: the complete current `TXT google._domainkey` value must be copied exactly from Namecheap and confirmed against authoritative DNS before delegation
- Calendly redirect: `book.fewshotsolutions.co` redirects unmasked to `https://calendly.com/isaac-fewshotsolutions/30min`

Cloudflare's automatic DNS import is not trusted as the sole source. Every imported record must be compared with the Namecheap inventory before nameservers change.

## Migration sequence

1. Add `fewshotsolutions.co` to the Cloudflare free plan and allow its initial DNS scan.
2. Compare every imported DNS record with the inventory above. Add or correct missing records before delegation.
3. Keep the apex and `www` website records DNS-only initially to avoid changing website behavior during the migration.
4. Recreate the `book` hostname as a proxied Cloudflare DNS record plus a Single Redirect Rule to the exact Calendly URL.
5. Change the domain's authoritative nameservers at Namecheap to the two nameservers assigned by Cloudflare.
6. Wait until public resolvers and the `.co` delegation return the Cloudflare nameservers, then verify the website, Google MX/SPF/DKIM/DMARC records, and Calendly redirect.
7. Create a named Cloudflare Tunnel for the Pi and install `cloudflared` as a system service using Cloudflare's generated tunnel token. The token must be stored only in the service configuration and must not be committed.
8. Publish `n8n.fewshotsolutions.co` through the tunnel to `http://127.0.0.1:5678`. Replace the temporary public-IP A record with the tunnel-managed DNS route.
9. Preserve the existing n8n public settings (`N8N_HOST`, `N8N_PROTOCOL`, and `WEBHOOK_URL`) and add the reverse-proxy hop setting required for the Cloudflare proxy. Restart only the n8n container.
10. Verify the editor sign-in page, TLS, webhook base URL, container health, and n8n logs from an independent public path.
11. Only after successful verification, remove router forwards for TCP 80/443 and disable Caddy. Retain the Caddy configuration temporarily for rollback.

## Security and availability

- Cloudflare Tunnel uses outbound-only connections from the Pi; the Pi no longer needs public inbound web ports.
- n8n retains its own authentication and secure cookies.
- Cloudflare Access will not be placed in front of the entire hostname because that would block third-party webhook delivery. Access controls can be designed separately later if editor-only protection is required.
- Existing PostgreSQL and pgAdmin ports are outside this migration and will not be changed.
- The tunnel service and n8n container must both start automatically after a Pi reboot.

## Validation checklist

- Cloudflare is authoritative for `fewshotsolutions.co`.
- Apex and `www` still reach `185.158.133.1`.
- Google MX, SPF, both verification records, DKIM, and DMARC match their pre-migration values.
- `book.fewshotsolutions.co` redirects to the existing Calendly URL.
- `https://n8n.fewshotsolutions.co/signin` returns HTTP 200 with a valid certificate.
- n8n health and container logs show no proxy or webhook errors.
- A test webhook is reachable through the public hostname.
- n8n and the tunnel recover after service restart; reboot verification is optional unless service-start behavior is uncertain.
- The public hostname still works after inbound router ports 80/443 are closed and Caddy is stopped.

## Rollback

Until final verification is complete, leave the Namecheap DNS records, Caddy configuration, and router forwards unchanged. If Cloudflare delegation causes a regression, restore Namecheap's original nameservers. If the tunnel fails after delegation, temporarily restore the `n8n` A record to the current public IP and re-enable Caddy while the tunnel issue is diagnosed.

## Out of scope

- Moving Docker or PostgreSQL data to external storage
- Redesigning n8n authentication or adding Cloudflare Access path policies
- Changing the main website hosting
- Changing Google Workspace configuration
- Exposing PostgreSQL or pgAdmin through Cloudflare Tunnel
