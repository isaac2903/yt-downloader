# Cloudflare Tunnel for n8n Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `https://n8n.fewshotsolutions.co` stable through public-IP changes by moving DNS to Cloudflare and routing the hostname through an outbound-only tunnel on the Raspberry Pi.

**Architecture:** Cloudflare becomes authoritative DNS for `fewshotsolutions.co` while Namecheap remains the registrar. A named `cloudflared` tunnel forwards the n8n hostname to `http://127.0.0.1:5678`; the existing website and Google Workspace records are copied unchanged, and the Namecheap Calendly redirect is recreated at Cloudflare's edge.

**Tech Stack:** Cloudflare DNS and Tunnel, Namecheap registrar, Raspberry Pi OS 12, systemd, Docker Compose, n8n, PostgreSQL, Caddy rollback path

## Global Constraints

- Do not change the main website hosting or Google Workspace configuration.
- Preserve every existing DNS record exactly before changing nameservers.
- Keep `@`, `www`, and the temporary `n8n` A record DNS-only during DNS migration.
- Do not paste or commit the Cloudflare tunnel token.
- Keep Caddy and router forwards active until the tunnel passes public verification.
- Do not expose PostgreSQL or pgAdmin through the tunnel.
- Place no Cloudflare Access policy in front of the entire n8n hostname because public webhooks must remain reachable.

---

### Task 1: Capture a pre-migration DNS and service baseline

**Files:**
- Read: `/home/raspberrypi/n8n/docker-compose.yml`
- Create locally: `/tmp/fewshotsolutions-namecheap-before.txt`

**Interfaces:**
- Consumes: Namecheap authoritative DNS and the live Pi services.
- Produces: A baseline used to reject an incomplete Cloudflare import and prove no regression.

- [ ] **Step 1: Save the authoritative DNS baseline**

Run locally:

```bash
{
  dig +noall +answer NS fewshotsolutions.co @dns1.registrar-servers.com
  dig +noall +answer A fewshotsolutions.co @dns1.registrar-servers.com
  dig +noall +answer A www.fewshotsolutions.co @dns1.registrar-servers.com
  dig +noall +answer A n8n.fewshotsolutions.co @dns1.registrar-servers.com
  dig +noall +answer A book.fewshotsolutions.co @dns1.registrar-servers.com
  dig +noall +answer MX fewshotsolutions.co @dns1.registrar-servers.com
  dig +noall +answer TXT fewshotsolutions.co @dns1.registrar-servers.com
  dig +noall +answer TXT _dmarc.fewshotsolutions.co @dns1.registrar-servers.com
  dig +noall +answer TXT google._domainkey.fewshotsolutions.co @dns1.registrar-servers.com
} | tee /tmp/fewshotsolutions-namecheap-before.txt
```

Expected: records for the website, n8n, Namecheap forwarding IP, Google MX, SPF, two Google verification values, DMARC, and the complete Google DKIM key.

- [ ] **Step 2: Record application health**

Run locally:

```bash
curl -fsSI https://fewshotsolutions.co/ | head
curl -fsSIL http://book.fewshotsolutions.co/ | grep -E 'HTTP/|[Ll]ocation:'
curl -fsS -o /dev/null -w 'n8n=%{http_code} tls=%{ssl_verify_result}\n' \
  'https://n8n.fewshotsolutions.co/signin?redirect=%252F'
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'systemctl is-active caddy docker; curl -fsS http://127.0.0.1:5678/healthz'
```

Expected: website responds, `book` returns a redirect to `https://calendly.com/isaac-fewshotsolutions/30min`, n8n returns `200` with `tls=0`, both services are active, and health is `{"status":"ok"}`.

### Task 2: Add the zone to Cloudflare without changing delegation

**Files:** None

**Interfaces:**
- Consumes: The baseline from Task 1 and the user's authenticated Cloudflare account.
- Produces: A complete inactive Cloudflare DNS zone and two assigned Cloudflare nameservers.

- [ ] **Step 1: Add the domain**

In Cloudflare, select **Domains → Add a domain**, enter `fewshotsolutions.co`, choose the **Free** plan, and allow the automatic DNS scan. Do not change Namecheap nameservers yet.

- [ ] **Step 2: Normalize the imported website records**

In **DNS → Records**, ensure these records exist and set **Proxy status** to **DNS only**:

```text
A  @    185.158.133.1  TTL Auto  DNS only
A  www  185.158.133.1  TTL Auto  DNS only
A  n8n  49.245.39.19   TTL Auto  DNS only
```

- [ ] **Step 3: Verify Google Workspace records**

Ensure Cloudflare contains:

```text
MX   @       smtp.google.com  Priority 1  TTL Auto
TXT  @       v=spf1 include:_spf.google.com ~all
TXT  @       google-site-verification=SaJLghOUWswqbrrBgTrAIv9_EccGGvTV8h1d82FSwC0
TXT  @       google-site-verification=xLkNTpTuPKgsz_c3LasmOrXFZwGGiDwnpmwQAaVvAH0
TXT  _dmarc  v=DMARC1; p=quarantine; rua=mailto:dmarc@fewshotsolutions.co; fo=1; pct=20
```

Open the `google._domainkey` TXT record in Namecheap and Cloudflare side by side. Copy the complete value without added or missing characters. Confirm it begins with `v=DKIM1; k=rsa; p=` and ends with `QIDAQAB`.

- [ ] **Step 4: Recreate the Calendly hostname**

Add this Cloudflare DNS record:

```text
A  book  192.0.2.1  TTL Auto  Proxied
```

Create **Rules → Redirect Rules → Single Redirect** with:

```text
Name: book to Calendly
Match: Hostname equals book.fewshotsolutions.co
Target URL: https://calendly.com/isaac-fewshotsolutions/30min
Status code: 302
Preserve query string: enabled
```

- [ ] **Step 5: Review before delegation**

Compare the Cloudflare DNS table line by line with `/tmp/fewshotsolutions-namecheap-before.txt`. Stop if any website, MX, SPF, verification, DMARC, or DKIM record is absent or different.

Expected: Cloudflare displays two assigned nameservers, but public `NS fewshotsolutions.co` still returns Namecheap.

### Task 3: Delegate DNS to Cloudflare and verify every existing service

**Files:** None

**Interfaces:**
- Consumes: The complete Cloudflare zone from Task 2.
- Produces: Cloudflare-authoritative DNS with the website, email, n8n, and Calendly behavior intact.

- [ ] **Step 1: Change nameservers at Namecheap**

In Namecheap, open **Domain List → Manage → Domain → Nameservers**, choose **Custom DNS**, enter exactly the two nameservers assigned by Cloudflare, save, and change nothing else.

- [ ] **Step 2: Poll delegation**

Run every few minutes:

```bash
dig +short NS fewshotsolutions.co @1.1.1.1
dig +short NS fewshotsolutions.co @8.8.8.8
```

Expected: both resolvers eventually return the two assigned Cloudflare nameservers. Do not continue while either resolver returns `registrar-servers.com`.

- [ ] **Step 3: Verify DNS records after delegation**

Run:

```bash
dig +short A fewshotsolutions.co @1.1.1.1
dig +short A www.fewshotsolutions.co @1.1.1.1
dig +short A n8n.fewshotsolutions.co @1.1.1.1
dig +short MX fewshotsolutions.co @1.1.1.1
dig +short TXT fewshotsolutions.co @1.1.1.1
dig +short TXT _dmarc.fewshotsolutions.co @1.1.1.1
dig +short TXT google._domainkey.fewshotsolutions.co @1.1.1.1
```

Expected: website A records are `185.158.133.1`, n8n is `49.245.39.19`, MX is priority `1 smtp.google.com.`, and all TXT values match the Task 1 baseline.

- [ ] **Step 4: Verify public behavior**

Run:

```bash
curl -fsSI --max-time 15 https://fewshotsolutions.co/ | head
curl -fsSIL --max-time 15 http://book.fewshotsolutions.co/ | grep -E 'HTTP/|[Ll]ocation:'
curl -fsS -o /dev/null -w 'n8n=%{http_code} tls=%{ssl_verify_result}\n' \
  --max-time 15 'https://n8n.fewshotsolutions.co/signin?redirect=%252F'
```

Expected: website responds, `book` reaches the exact Calendly URL, and n8n returns `200` with `tls=0`. If email DNS differs, restore Namecheap nameservers immediately. If only a web route fails, correct that Cloudflare record before proceeding.

### Task 4: Create and install the named Cloudflare Tunnel

**Files:**
- Create on Pi: Cloudflare-managed `cloudflared.service` configuration

**Interfaces:**
- Consumes: The active Cloudflare zone and local n8n at `http://127.0.0.1:5678`.
- Produces: A persistent outbound tunnel connected to Cloudflare.

- [ ] **Step 1: Create the tunnel in Cloudflare**

Open **Zero Trust → Networks → Tunnels** (or **Networking → Tunnels** in the current dashboard), choose **Create a tunnel → Cloudflared**, name it `raspberrypi-n8n`, and choose the Debian ARM64 connector instructions.

- [ ] **Step 2: Install the connector package on the Pi**

Open an SSH shell on the Pi:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26
```

Install `cloudflared` from Cloudflare's stable Debian Bookworm repository:

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main' \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install -y cloudflared
exit
```

Then verify:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'cloudflared --version'
```

Expected: a `cloudflared version` line and exit code `0`.

- [ ] **Step 3: Install the tunnel token as a service**

Cloudflare displays a complete `sudo cloudflared service install` command followed by an opaque tunnel token. Copy the complete command from the dashboard and run it directly in an SSH session on the Pi. Do not paste the token into chat, a repository file, shell history shared with others, or the n8n `.env` file.

Verify:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'systemctl is-enabled cloudflared; systemctl is-active cloudflared; journalctl -u cloudflared -n 30 --no-pager'
```

Expected: `enabled`, `active`, and at least one registered tunnel connection without authentication errors.

- [ ] **Step 4: Configure the public hostname**

In the tunnel's **Public Hostnames** section, add:

```text
Subdomain: n8n
Domain: fewshotsolutions.co
Path: empty
Service type: HTTP
URL: localhost:5678
```

When Cloudflare reports that an `n8n` DNS record already exists, delete only the temporary `A n8n 49.245.39.19` record and save the public hostname again. Confirm Cloudflare creates a proxied tunnel CNAME for `n8n`.

### Task 5: Make n8n proxy-aware and validate the tunnel

**Files:**
- Modify on Pi: `/home/raspberrypi/n8n/docker-compose.yml`

**Interfaces:**
- Consumes: The active tunnel from Task 4.
- Produces: n8n with correct proxy trust, HTTPS cookies, URLs, and webhook behavior.

- [ ] **Step 1: Back up the Compose configuration**

Run:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'cp /home/raspberrypi/n8n/docker-compose.yml /home/raspberrypi/n8n/docker-compose.yml.pre-cloudflare'
```

- [ ] **Step 2: Add the proxy hop setting**

Under the existing n8n `environment:` list, preserve the current hostname settings and add exactly:

```yaml
- N8N_PROXY_HOPS=1
```

The relevant resulting environment must contain:

```yaml
- N8N_HOST=n8n.fewshotsolutions.co
- N8N_PORT=5678
- N8N_PROTOCOL=https
- WEBHOOK_URL=https://n8n.fewshotsolutions.co/
- N8N_PROXY_HOPS=1
```

- [ ] **Step 3: Validate Compose before restarting**

Run:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'cd /home/raspberrypi/n8n && sudo docker compose config --quiet'
```

Expected: exit code `0` and no output.

- [ ] **Step 4: Restart only n8n**

Run:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'cd /home/raspberrypi/n8n && sudo docker compose up -d --no-deps n8n'
```

Expected: PostgreSQL and pgAdmin are not recreated; `n8n-n8n-1` becomes `Up`.

- [ ] **Step 5: Verify local and public health**

Run:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'curl -fsS http://127.0.0.1:5678/healthz; sudo docker logs --since 2m n8n-n8n-1 2>&1 | tail -80'
curl -fsS -o /dev/null -w 'status=%{http_code} tls=%{ssl_verify_result} remote=%{remote_ip}\n' \
  --max-time 15 'https://n8n.fewshotsolutions.co/signin?redirect=%252F'
```

Expected: local health is `{"status":"ok"}`, public sign-in is `200` with `tls=0`, the remote IP belongs to Cloudflare rather than the home ISP, and logs contain no startup or proxy errors.

- [ ] **Step 6: Verify one webhook**

Open an existing webhook workflow in n8n, choose **Listen for Test Event**, copy the complete Test URL displayed by n8n, and invoke that exact URL from its source or with `curl`. Confirm the copied URL begins with `https://n8n.fewshotsolutions.co/webhook-test/`. Expected: n8n records the test event and the caller receives the workflow's configured response. Do not create or activate a new production workflow solely for this test.

### Task 6: Remove the old public ingress only after tunnel success

**Files:**
- Preserve on Pi: `/etc/caddy/Caddyfile`
- Change on Pi: `caddy.service` enabled/running state
- Change on router: TCP 80/443 forwarding rules

**Interfaces:**
- Consumes: Successful Task 5 public editor and webhook verification.
- Produces: An outbound-only n8n deployment with no direct home-IP web ingress.

- [ ] **Step 1: Disable Caddy without deleting its configuration**

Run:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'sudo systemctl disable --now caddy; systemctl is-active caddy || true; systemctl is-enabled caddy || true'
```

Expected: `inactive` and `disabled`; `/etc/caddy/Caddyfile` remains present.

- [ ] **Step 2: Verify the tunnel still serves n8n**

Run:

```bash
curl -fsS -o /dev/null -w 'status=%{http_code} tls=%{ssl_verify_result}\n' \
  --max-time 15 'https://n8n.fewshotsolutions.co/signin?redirect=%252F'
```

Expected: `status=200 tls=0`. If it fails, re-enable Caddy with `sudo systemctl enable --now caddy` and diagnose before touching the router.

- [ ] **Step 3: Remove router forwards**

In the router administration page, remove or disable only the TCP port-forward rules that send WAN ports `80` and `443` to `192.168.50.26`. Do not change Tailscale, SSH, Wi-Fi, DHCP reservation, or unrelated forwards.

- [ ] **Step 4: Run final verification**

Run:

```bash
curl -fsSI --max-time 15 https://fewshotsolutions.co/ | head
curl -fsSIL --max-time 15 http://book.fewshotsolutions.co/ | grep -E 'HTTP/|[Ll]ocation:'
curl -fsS -o /dev/null -w 'n8n=%{http_code} tls=%{ssl_verify_result}\n' \
  --max-time 15 'https://n8n.fewshotsolutions.co/signin?redirect=%252F'
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'systemctl --failed --no-legend; systemctl is-active cloudflared docker; systemctl is-enabled cloudflared; curl -fsS http://127.0.0.1:5678/healthz; sudo docker ps --format "{{.Names}}|{{.Status}}"'
```

Expected: website and Calendly work, n8n is `200` with valid TLS, no failed system units exist, `cloudflared` and Docker are active, `cloudflared` is enabled, n8n health is OK, and all three n8n stack containers are Up.

### Task 7: Record rollback state and stop

**Files:**
- Retain on Pi: `/home/raspberrypi/n8n/docker-compose.yml.pre-cloudflare`
- Retain on Pi: `/etc/caddy/Caddyfile`

**Interfaces:**
- Consumes: The verified final deployment.
- Produces: A reversible handoff without unrelated cleanup.

- [ ] **Step 1: Confirm rollback assets remain**

Run:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'test -f /home/raspberrypi/n8n/docker-compose.yml.pre-cloudflare && test -f /etc/caddy/Caddyfile && echo rollback-assets-present'
```

Expected: `rollback-assets-present`.

- [ ] **Step 2: Document the rollback order in the handoff**

If rollback is required later:

```text
1. Re-enable Caddy.
2. Restore the n8n A record to the current home public IP.
3. Reopen router ports 80/443 only if direct ingress is intentionally restored.
4. If Cloudflare DNS itself is the failure, restore Namecheap's original nameservers.
5. Restore docker-compose.yml.pre-cloudflare only if the n8n proxy setting caused the regression.
```

Do not remove Cloudflare DNS, Caddy configuration, or the Compose backup as part of this migration.
