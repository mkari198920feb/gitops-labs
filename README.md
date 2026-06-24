
#MCP
This is a small MCP server I built to poke at ArgoCD from inside a Claude
chat instead of switching between the CLI and the UI every time I want to
check on something. It exposes ArgoCD's REST API as a handful of tools —
list apps, get status, look at the resource tree, trigger a sync, roll
back a bad deploy — and Claude calls them directly.

I built this mostly to actually understand MCP rather than just read about
it. The whole thing runs locally: a kind cluster on my laptop, ArgoCD
installed into it, a tiny nginx app deployed via GitOps from this repo
(`apps/demo-nginx`), and this server sitting between Claude Desktop and
ArgoCD's API.

It is not production-hardened. It uses the ArgoCD admin account, skips TLS
verification (self-signed cert on a local cluster), and has no auth layer
of its own — Claude Desktop just launches it as a subprocess and talks to
it over stdio. Fine for a lab on my own machine, not something I'd point at
a real cluster without changes. More on that below.

## How it's wired together
Claude Desktop

|  stdio / JSON-RPC

v

src/server.py            (tool definitions + routing)

v

src/argocd_client.py      (httpx calls to ArgoCD's REST API)

v

ArgoCD (localhost:8080, via kubectl port-forward)

v

kind cluster running demo-nginx

## Tools

Six tools right now, all ArgoCD. Four are read-only and safe to call
anytime — `argocd_list_applications`, `argocd_get_application`,
`argocd_get_resource_tree`, `argocd_get_events`. The other two actually
change cluster state:

- `argocd_sync_application` — defaults to `dry_run=True`, so calling it
  without thinking shows you what *would* happen rather than doing it.
  Set `dry_run=False` to apply for real.
- `argocd_rollback_application` — rolls back to a specific revision ID
  from the app's history.

Both are flagged as destructive in their tool descriptions, and Claude
Desktop's "needs approval" setting means you get a confirmation prompt
before either one actually fires. That's the real safety net here, not
the dry-run default — don't rely on the default alone if you ever loosen
the approval setting.

## Getting it running

You'll need Python 3.10+, an ArgoCD instance you can reach (I'm running
mine in a local `kind` cluster, port-forwarded to `localhost:8080`), and
the actual Claude Desktop app — not claude.ai in a browser. The browser
version has no way to launch a local process over stdio, which tripped me
up for a good twenty minutes before I realized I'd never actually installed
the desktop app.

```bash
git clone https://github.com/mkari198920feb/gitops-labs.git
cd gitops-labs/mcp-server

python3 -m venv .venv
source .venv/bin/activate
pip install mcp httpx python-dotenv
```

If pip complains about not being able to uninstall PyJWT (this happened to
me — some systems have a Debian-packaged PyJWT that pip can't touch),
add `--ignore-installed pyjwt` to the install command.

Create a `.env` file (it's gitignored, don't worry about committing it by
accident, but double check anyway):
ARGOCD_BASE_URL=https://localhost:8080

ARGOCD_TOKEN=

To get a token, the admin account needs apiKey capability first — mine
didn't have it by default and `argocd account generate-token` failed with
"account does not have apiKey capability" until I ran:

```bash
kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"accounts.admin":"apiKey,login"}}'
kubectl rollout restart deployment argocd-server -n argocd
```

Then, with the port-forward running:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
argocd login localhost:8080 --username admin --password '<your password>' --insecure
argocd account generate-token --account admin
```

That token only shows once — paste it straight into `.env`, you can't
retrieve it later if you lose it (found that out the hard way, had to
regenerate).

Quick sanity check that the server itself runs:

```bash
python3 -m src.server
```

It should just sit there waiting on stdin. That's correct — Ctrl+C out of
it. If you want to see an actual response, this sends a fake initialize +
tools/list over stdin:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python3 -m src.server
```

You should get back JSON listing all six tools.

## Hooking it into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) — create the file if it doesn't exist — and add:

```json
{
  "mcpServers": {
    "devops-mcp": {
      "command": "/Users/muralikrishnak/.docker/devops-mcp/.venv/bin/python3",
      "args": ["-m", "src.server"],
      "cwd": "/Users/muralikrishnak/.docker/devops-mcp",
      "env": {
        "PYTHONPATH": "/Users/muralikrishnak/.docker/devops-mcp",
        "ARGOCD_BASE_URL": "https://localhost:8080",
        "ARGOCD_TOKEN": "your-token-here"
      }
    }
  }
}
```

Two things that bit me here and cost some debugging time:

- Point `command` at the venv's actual python3 binary, full path, not just
  `python3`. Claude Desktop spawns this as a subprocess without your
  shell's virtualenv activated, so a bare `python3` resolves to system
  Python, which doesn't have `mcp` or `httpx` installed.
- I had `cwd` missing from my config at one point (not sure how — might
  have gotten dropped during an edit) and got
  `ModuleNotFoundError: No module named 'src'` even though running the
  exact same command manually from my terminal worked fine. Setting both
  `cwd` and `PYTHONPATH` to the project directory fixed it. Belt and
  suspenders, but it works.

After editing the config, fully quit Claude Desktop — actually quit
(Cmd+Q), not just close the window, or it won't reload the config — and
reopen it. Go to the `+` icon next to the message box → Manage connectors,
and `devops-mcp` should show up with all six tools listed.

## Using it

With ArgoCD up and `demo-nginx` deployed (see `apps/demo-nginx` in this
repo), you can just ask Claude things like:

- "List my ArgoCD applications"
- "Is demo-nginx in sync?"
- "Show me the resource tree for demo-nginx"
- "Do a dry-run sync on demo-nginx, what would change"

First time you ask for something that calls a tool, you'll get an
approval prompt — that's expected, it's set to "needs approval" by
design.

## Things I know are rough edges

- Using the admin account directly instead of a scoped service account.
  Fine for a single-developer lab, wouldn't do this anywhere shared.
- `verify=False` on every httpx call because of the self-signed cert.
  Don't copy this pattern if you ever point this at a real cluster.
- No retry/backoff logic anywhere — if ArgoCD is slow or the port-forward
  hiccups, you just get an error back, no graceful handling.

## Layout
mcp-server/

src/

server.py          - MCP entrypoint, tool schemas, routes calls

argocd_client.py    - the actual httpx calls to ArgoCD

tools/

init.py

.gitignore

README.md
