---
name: alza
description: Search alza.cz products, fetch a product's price and availability, or check the user's Alza account status from the terminal. Use when asked to look something up on Alza, compare Alza prices, check if Alza has something in stock, or paste a fresh Alza token.
---

# Alza.cz search

CLI at `~/code/alza/alza.py` (README there). Run it with Bash from any directory; `uv` resolves the deps.

```
~/code/alza/alza.py search "<query>" [--page N] [--sort price-asc|price-desc|rating|newest] [--json]
~/code/alza/alza.py product <id|url> [--json]
~/code/alza/alza.py me [--json]
~/code/alza/alza.py token   # stdin: a browser "copy as curl" containing the bearer
```

## Rules

- Use the CLI, never curl or WebFetch: Cloudflare 403s them on the TLS fingerprint. The CLI's
  `curl_cffi` Chrome impersonation is what gets through.
- Search with `--json` when you need to reason over results; the plain output is for showing the user.
- Queries are Czech-friendly; a generic term redirects to a category page and returns that category's
  listing (the `title` and `url` in the output say which). A specific term returns a "Vyhledáno:" page.
- Prices are CZK. `coupon_price` + `coupon_code` is the price after an Alza discount code
  (`AlzaPlus` means the AlzaPlus member price). `availability` is Alza's own label ("Skladem > 5 ks",
  "Rozbaleno", "Na objednávku"). The search label is more precise than the product page's
  schema.org `InStock`, which is also set for items still on the way.
- `me` needs a bearer token in `~/.config/alza/token`; it lives 90 minutes. If the CLI says expired,
  ask the user for a fresh browser curl (DevTools > Network > any `/api/` request > Copy as cURL) and
  pipe it to `alza.py token`. Never print the token and never write it into a repo.
- Read-only. Do not add basket or order actions without asking.
