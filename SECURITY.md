# QuantPilot Security Policy & Guidelines

QuantPilot is a quantitative trading research and decision-support platform hosted in a **PUBLIC GitHub repository** ([https://github.com/kingofrajgit/QuantPilot](https://github.com/kingofrajgit/QuantPilot)).

Because this repository is public, strict security controls are mandatory for all contributors, commits, automated pipelines, and testing environments.

---

## 1. Absolute Rule: No Hardcoded Secrets

**Never commit, hardcode, or track any credential, secret, private key, token, or connection string in Git.**

This rule applies to all credentials without exception, including:
- Development, local, sandbox, and paper-trading credentials.
- AI API keys (e.g., Anthropic Claude, OpenAI).
- Broker credentials (e.g., Zerodha Kite API keys, secrets, tokens).
- Database credentials and connection URLs.
- Telegram/webhook tokens.
- Private encryption keys (`*.pem`, `*.key`, `*.p12`, `*.pfx`).

A credential being "only for testing" or "temporary" does **NOT** make it safe to commit.

---

## 2. Environment Variables & `.env` File Usage

All runtime credentials must be supplied exclusively through environment variables:
1. **Local Development**: Configure secrets in a local `.env` file in the root of the repository.
2. **Git Tracking**: `.env` and `.env.*` are strictly ignored by `.gitignore` and must **never** be committed.
3. **Template**: `.env.example` is tracked in the repository and provides example keys with clearly fake placeholders (e.g., `your-anthropic-api-key-here`). Real values must never appear in `.env.example`.
4. **No Required Credentials at Startup**: The application and test suite can be imported and initialized without any credentials. Secrets are validated lazily only by components that strictly require them at runtime.
5. **Fail-Closed Principle**: If a required credential is missing when a component executes, it fails closed with a `ConfigurationError`. **No fallback secrets (e.g., `os.getenv("KEY", "default-secret")`) are permitted under any circumstances.**

---

## 3. Broker Credential Security (Zerodha)

1. Zerodha credentials (`ZERODHA_API_KEY`, `ZERODHA_API_SECRET`, `ZERODHA_ACCESS_TOKEN`) must only be read through the centralized configuration layer (`quantpilot.config.Settings`).
2. The Zerodha account password must **never** be stored, requested, or processed by QuantPilot.
3. Architecture boundary:
   ```
   .env / Environment
         ↓
   quantpilot.config.Settings
         ↓
   Broker Interface (quantpilot.broker.Broker)
         ↓
   ZerodhaBroker Adapter (Safety Barrier)
         ↓
   Future Kite API Client
   ```
4. In this bootstrap phase, live order execution is strictly disabled. The default broker is `SimulatedBroker`, which requires no credentials and performs no network calls.

---

## 4. AI API Credential Security (Anthropic Claude)

1. Claude API keys must be loaded from `ANTHROPIC_API_KEY`.
2. Never store AI keys in notebooks, prompt files, YAML configs, Dockerfiles, or pull request descriptions.
3. In CI/CD pipelines, configure keys through GitHub Repository Secrets or environment secrets, never in workflow YAML files.

---

## 5. Local Development & Testing Security

1. **Default Test Suite**: Running `python -m pytest -v` requires zero external credentials and makes zero network calls.
2. **Deterministic Simulation**: All unit tests run against `SimulatedBroker` using synthetic data and in-memory balances.
3. **Real Money Guard**: Tests must **never** place, modify, or cancel live broker orders or transfer funds.
4. **External Integration Tests**:
   - Integration tests requiring external services must be explicitly decorated with:
     ```python
     @pytest.mark.external
     @pytest.mark.integration
     ```
   - If required credentials are not found in the environment, the test must **skip cleanly** (`pytest.skip()`), never fail, and never substitute mock credentials as live keys.

---

## 6. Paper vs. Live Separation

QuantPilot enforces a strict multi-tier progression:
```
Development (SimulatedBroker)
      ↓
Backtest (Historical Simulation)
      ↓
Paper Trading (Simulated Execution + Real Market Data)
      ↓
Validation & Risk Gate
      ↓
Explicit Live Authorization (LIVE_TRADING_ENABLED=true)
```
- `LIVE_TRADING_ENABLED` defaults strictly to `false`.
- The presence of valid Zerodha credentials does **not** enable live trading.
- Live trading requires an explicit, intentional configuration toggle and safety checks.

---

## 7. Sanitization & Log Protection

1. Sensitive tokens (Bearer tokens, Authorization headers, database passwords, API keys) must be sanitized before writing to logs, exceptions, or console output.
2. QuantPilot includes `quantpilot.security.sanitizer.SecurityLogFilter` and `sanitize_text()` to scrub credentials automatically.

---

## 8. GitHub Secret Scanning & Push Protection

1. Repository-level automated tests check for committed keys and verify `.gitignore` integrity.
2. CI runs [Gitleaks](https://github.com/gitleaks/gitleaks) on every push and pull request to detect accidental credential leaks before merging.
3. Contributors should enable GitHub Secret Scanning and Push Protection in their personal forks.

---

## 9. Incident Response: Leaked Credential Procedure

If a secret or credential is ever accidentally committed to the repository:

1. **IMMEDIATELY REVOKE THE CREDENTIAL**:
   - For broker credentials: log into the broker portal immediately and regenerate or invalidate the API key and secret.
   - For AI API keys: revoke the key immediately in the provider dashboard (e.g., Anthropic Console).
   - For database/server secrets: rotate passwords and terminate active sessions immediately.
   - *Treat any committed credential as compromised instantly, even if the commit was quickly amended or deleted.*
2. **Scrub Git History**:
   - Use `git-filter-repo` or BFG Repo-Cleaner to completely remove the commit from git history.
   - Force-pushing without scrubbing history leaves the secret accessible in past commits.
3. **Report the Incident**:
   - Notify the repository maintainers immediately.
