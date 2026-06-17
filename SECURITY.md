# Security Policy

## Reporting security issues

If you discover a security issue in WB Radar & China Matcher, please open a
private issue or email the maintainer directly instead of posting publicly.
Do not attach logs that contain API keys, cookies, or session files.

## Secrets handling

- **Never commit real API keys, tokens, cookies, or session data.**
- Secrets are read from `.env` / `.env.local` or environment variables only.
- `.env.example` contains empty placeholders and is safe to commit.
- The application reads keys such as `OPENROUTER_API_KEY`, `ZAI_API_KEY`, and
  `GROQ_API_KEY` at runtime; these values are not logged or printed.

## What is not tracked

The following files and directories are intentionally excluded from version
control by `.gitignore`:

- `.env` and `.env.local`
- `.venv/`
- `sessions/`
- `output/`
- `build/` and `dist/`
- `*.exe`
- `*.db`
- `__pycache__/` and `.pytest_cache/`
- `handoff_f15_sa*.md` local handoff files

If you accidentally committed any of the above, rotate the exposed credentials
and remove the files from git history before pushing.

## Live tests and network access

Tests marked `@pytest.mark.live` require explicit environment flags to run:

```powershell
$env:WB_RADAR_RUN_LIVE = "1"
python -m pytest -m live -q
```

Without the flag, live tests are skipped automatically. Live tests may contact
public Wildberries endpoints and China marketplaces. They do not bypass captchas
or anti-bot protections.

## Anti-bot / captcha policy

This project does **not** bypass captchas, WAF, or anti-bot systems. If a site
shows a challenge, the tool logs the event and either asks the user to solve it
manually or skips the source.

## Third-party content

Video reviews from Wildberries and product videos from China marketplaces are
used as reference material only. They are not re-uploaded 1:1. Generated
hooks, descriptions, and VoC analysis are the user's own content.

## Disclaimer

Use of public Wildberries endpoints is governed by Wildberries terms of service.
Use of China marketplace search and video extraction is governed by the
respective platforms' terms. This tool is provided as-is for legitimate
product research and sourcing workflows.
