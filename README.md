# alza

Alza.cz from the terminal: product search and product detail. No login, no token.

```
./alza.py search "oral-b io 10" [--page 2] [--sort price-asc|price-desc|rating|newest] [--json]
./alza.py product 7274516            # numeric id or an alza.cz product URL
```

Runs with `uv` (inline script metadata: curl_cffi, beautifulsoup4). No install step.

## Install

```
git clone https://github.com/pepijnsenders/alza-cli ~/code/alza
~/code/alza/alza.py search "yamaha ns-aw294"
```

## Claude Code skill

`skill/SKILL.md` teaches Claude Code to use the CLI (and to never fall back to curl or WebFetch,
which Cloudflare blocks). Link it into your skills directory and invoke it with `/alza <question>`:

```
ln -s ~/code/alza/skill ~/.claude/skills/alza
```

## How it gets past Cloudflare

alza.cz sits behind a Cloudflare managed challenge that keys on the TLS fingerprint.
Plain curl, WebFetch and crawler user agents (ClaudeBot, GPTBot, Googlebot, ...) all get
a 403 challenge page. `curl_cffi` with `impersonate="chrome"` passes with no cookies at all,
from a datacenter IP.

## Endpoints used

| Purpose | Call |
| --- | --- |
| Search landing | `GET /search.htm?exps=<q>` (may 302 to a category page) |
| Paging and sorting | `POST /Services/EShopService.svc/Filter` with the `_pageData.data` fields from the landing page; needs the warm session cookies from that GET |
| Product | `GET /product-d<id>.htm` (redirects to the canonical URL), parsed from the `Product` JSON-LD |

Sort codes: 0 default, 1 price ascending, 2 price descending, 6 rating, 5 newest.
The Filter `inStock` flag does not filter, so there is no in-stock option.


## License

MIT.
