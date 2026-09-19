# QuantPilot

**QuantPilot** is an AI-assisted quantitative trading research and decision-support platform.

> [!WARNING]
> **DISCLAIMER & RISK NOTICE**:
> QuantPilot does not guarantee trading profits or investment returns. Quantitative trading involves significant financial risk and market exposure. Live trading is strictly **disabled by default** (`LIVE_TRADING_ENABLED=false`). Always test thoroughly in simulation and paper trading environments.

---

## Decision & Execution Pipeline

QuantPilot enforces a deterministic, multi-tier execution hierarchy where AI serves solely as an advisory and analytical layer, never directly executing trades:

```
                  ┌──────────────────────┐
                  │       AI Model       │
                  │ (Analysis / Proposal)│
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Quantitative Evidence│
                  │ (Backtest / Metrics) │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Deterministic        │
                  │ Validation           │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │     Risk Engine      │
                  │  (Limits / Exposure) │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │   Execution Policy   │
                  │    & Kill Switch     │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │   Broker Interface   │
                  │  (Simulated / Live)  │
                  └──────────────────────┘
```

---

## Mandatory Security Principles

QuantPilot is hosted in a **public GitHub repository**. The following rules are strictly enforced:

- **No Hardcoded Secrets**: Real API keys, tokens, passwords, and private keys must **never** be committed to Git.
- **Environment Configuration**: All credentials must be loaded via local environment variables or a local `.env` file.
- **`.env` is Ignored**: The `.env` file is excluded in `.gitignore` and must never be tracked.
- **`.env.example`**: Tracked in Git with dummy placeholders only (`your-api-key-here`).
- **Zero Startup Credentials Required**: QuantPilot boots and runs tests without requiring real credentials or network access.
- **Fail-Closed Security**: Missing credentials result in an immediate operation refusal with no insecure fallback defaults.
- **Simulated Broker by Default**: The current phase provides `SimulatedBroker` for local development, deterministic unit testing, and backtesting without real money or external dependencies.

---

## Getting Started

### Prerequisites
- Python 3.10+
- Git

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/kingofrajgit/QuantPilot.git
   cd QuantPilot
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .[dev]
   ```

4. **Configure environment variables (optional for development)**:
   ```bash
   cp .env.example .env
   # Edit .env with your local development keys if needed
   ```

---

## Running Tests & Quality Checks

### Run Unit & Security Tests
No credentials or external services are needed:
```bash
python -m pytest -v
```

### Run External Integration Tests (Opt-In)
External integration tests check for real credentials in the environment and skip safely if absent:
```bash
python -m pytest -m external -v
```

### Code Formatting and Linting
```bash
ruff check .
ruff format --check .
```

---

## Repository Structure

```
QuantPilot/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated CI: Secret detection, lint, tests
├── src/
│   └── quantpilot/
│       ├── __init__.py
│       ├── exceptions.py          # Centralized error hierarchy
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py        # Centralized settings with fail-closed validation
│       ├── security/
│       │   ├── __init__.py
│       │   └── sanitizer.py       # Credential and log sanitization utilities
│       └── broker/
│           ├── __init__.py
│           ├── base.py            # Broker interface, Order, Position, AccountBalance
│           ├── simulated.py       # Deterministic in-memory simulated broker
│           └── zerodha.py         # Safe adapter boundary (live execution disabled)
├── tests/
│   ├── conftest.py                # Isolated test environment and fixtures
│   ├── unit/
│   │   ├── test_config.py         # Config validation and secret redaction tests
│   │   ├── test_broker.py         # SimulatedBroker and live-barrier safety tests
│   │   └── test_security.py       # Secret detection and log sanitization tests
│   └── integration/
│       └── test_external_optin.py # Safe skip behavior for external integrations
├── .env.example                   # Template configuration with safe placeholders
├── .gitignore                     # Comprehensive gitignore for secrets and data
├── pyproject.toml                 # Package definition and tool configurations
├── SECURITY.md                    # Comprehensive security policy and incident response
└── README.md                      # Project documentation and guidelines
```

---

## Current Status: Phase 1 Bootstrap

- [x] Public repository security foundation & `.gitignore`
- [x] Centralized configuration management with fail-closed security
- [x] Deterministic `SimulatedBroker` implementation
- [x] `ZerodhaBroker` safe boundary (live order execution disabled)
- [x] Security sanitization utility for logs and exceptions
- [x] Automated test suite & CI workflow with secret scanning
- [ ] *Future Phases*: Market data ingestion, Backtesting engine, Paper trading, Quantitative strategies.
