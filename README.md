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
│       ├── broker/
│       │   ├── __init__.py
│       │   ├── base.py            # Broker interface, Order, Position, AccountBalance
│       │   ├── simulated.py       # Deterministic in-memory simulated broker
│       │   └── zerodha.py         # Safe adapter boundary (live execution disabled)
│       └── market_data/
│           ├── __init__.py
│           ├── models.py              # Canonical models (Instrument, Candle, Quote, Tick)
│           ├── validation.py          # Deterministic validation, gap and staleness checks
│           ├── base.py                # MarketDataProvider abstract base class
│           ├── mock.py                # Deterministic in-memory mock provider
│           ├── zerodha.py             # Safe Zerodha boundary (live ingestion disabled)
│           ├── historical_models.py   # HistoricalDatasetMetadata model
│           ├── historical_base.py     # HistoricalDataProvider and HistoricalDataStore ABCs
│           ├── parquet_store.py       # ParquetHistoricalDataStore with idempotent merging
│           ├── local_provider.py      # LocalHistoricalDataProvider
│           ├── repository.py          # HistoricalDataRepository query layer
│           └── zerodha_historical.py  # Safe Zerodha historical boundary
├── tests/
│   ├── conftest.py                # Isolated test environment and fixtures
│   ├── unit/
│   │   ├── test_config.py         # Config validation and secret redaction tests
│   │   ├── test_broker.py         # SimulatedBroker and live-barrier safety tests
│   │   ├── test_market_data.py    # Canonical models, OHLC validation, duplicates, staleness
│   │   ├── test_historical.py     # Parquet storage, idempotency, repository queries
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

## Market Data Architecture

QuantPilot processes market data through a provider-independent canonical pipeline. Downstream quantitative analysis and risk validation consume only canonical, validated data structures:

```
          ┌─────────────────────────┐
          │  Market Data Provider   │
          │  (Mock / Synthetic /    │
          │   Future Zerodha)       │
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │      Normalization      │
          │  (Timezone-aware UTC)   │
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │ Canonical Market Models │
          │(Instrument,Candle,Quote)│
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │     Data Validation     │
          │(OHLC, Order, Duplicates)│
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │   Data Quality Report   │
          │(VALID/STALE/INVALID/GAP)│
          └────────────┬────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │  Downstream Consumers   │
          │ (Quant Validation/Risk) │
          └─────────────────────────┘
```

> [!NOTE]
> **Phase 2A Status**:
> - External market-data providers and live WebSocket streaming are **intentionally not connected yet**.
> - All tests and development currently use synthetic/mock data generated deterministically via `MockMarketDataProvider`.
> - `ZerodhaMarketDataAdapter` acts strictly as an architectural placeholder boundary; live data ingestion will be implemented in a future approved phase.
> - Live trading remains strictly **disabled** (`LIVE_TRADING_ENABLED=false`).

---

## Historical Market Data & Storage (Phase 2B)

QuantPilot provides an offline, provider-independent historical OHLCV data pipeline:

```
          ┌───────────────────────────┐
          │  Historical Data Source   │
          │(Local Parquet/Mock/Future)│
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │  HistoricalDataProvider   │
          │    (Provider Interface)   │
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │     Canonical Candle      │
          │  (Timezone-aware UTC Bar) │
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │    Phase 2A Validation    │
          │ (validate_candles Engine) │
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │    HistoricalDataStore    │
          │ (Parquet Partition Store) │
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │ HistoricalDataRepository  │
          │ (High-Level Query Engine) │
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │ Downstream Quant Engines  │
          │(Backtest / Research / Risk)│
          └───────────────────────────┘
```

- **Provider Abstraction**: Decouples retrieval parameters from physical file layouts or vendor APIs.
- **Parquet Storage**: Local storage engine partitioned logically by `{exchange}/{symbol}/{timeframe}/data.parquet`.
- **Validation Before Persistence**: Enforces Phase 2A data quality rules (`validate_candles`) prior to disk writes.
- **Idempotent Ingestion**:
  - Exact duplicates on canonical key `(symbol, exchange, timeframe, timestamp)` are merged idempotently without duplication.
  - Conflicting records for an existing key trigger `DataConflictError`.
  - Genuinely new bars are appended and sorted chronologically.
- **Query Repository**: High-level repository exposing `get_candles()`, `has_data()`, and `get_metadata()`, completely abstracting away filesystem mechanics.
- **Deferred Zerodha Ingestion**: `ZerodhaHistoricalDataProvider` acts strictly as an architectural placeholder boundary; live Zerodha historical-data retrieval is intentionally deferred to a future approved phase.

---

## Historical Data Ingestion & Dataset Management (Phase 2C)

QuantPilot provides an atomic, offline historical market data ingestion pipeline supporting local CSV and Parquet sources:

```
          ┌───────────────────────────┐
          │   Raw File (CSV/Parquet)  │
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │     Ingestion Service     │
          │(HistoricalDataIngestion..)│
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │  Normalization & Parsing  │
          │(UTC Timestamp, Finite OHLC│
          │ Positive P, Non-negative V│
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │     Canonical Candle      │
          │    (Phase 2A Models)      │
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │    In-Batch & In-Store    │
          │  Deduplication & Conflict │
          └─────────────┬─────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
 [Conflict/Failure]             [Zero Conflicts]
         │                             │
         ▼                             ▼
 ┌───────────────┐             ┌───────────────┐
 │  ABORT WRITE  │             │ Atomic Staged │
 │   0 Written   │             │ Write & Commit│
 │ Status=FAILED │             │Status=SUCCESS │
 └───────────────┘             └───────┬───────┘
                                       │
                                       ▼
                               ┌───────────────┐
                               │IngestionReport│
                               │& Coverage Stat│
                               └───────────────┘
```

### Core Invariants & Architecture
- **Atomic All-or-Nothing Persistence**: If *any* parse error, validation failure, or data conflict is encountered in an ingestion batch, **zero candles are written** to storage and status is reported as `FAILED`.
- **True Atomic Persistence**: Storage uses a staged write-and-replace transaction mechanism (`manifest.json` pointer). A failure before commit leaves the existing store 100% untouched and leaves no orphan temporary files.
- **Idempotent Deduplication**: Identical existing records are skipped cleanly without duplicating entries. Conflicting records for an existing key trigger an atomic abort.
- **Strict OHLCV Semantics**: Enforces $O, H, L, C > 0$, $V \ge 0$, and strictly rejects non-finite values (`NaN`, `+Infinity`, `-Infinity`).
- **UTC Timezone Enforcement**: Naive timestamps are rejected unless `source_timezone` is explicitly specified. All timestamps are stored in UTC.
- **Conservative Coverage Reporting**: Timeframe-based chronological gap detection.
  > *Phase 2C does not yet provide exchange-calendar-aware gap classification. Gap detection is chronological/timeframe based and should be interpreted as a potential data-quality indicator.*
- **Deterministic Path Portability**: Relative application paths resolve deterministically against `PROJECT_ROOT = Path(__file__).resolve().parents[3]` regardless of the current working directory.
- **CLI Interface**:
  ```bash
  quantpilot data ingest \
    --source ./data/sample.csv \
    --format csv \
    --symbol RELIANCE \
    --exchange NSE \
    --timeframe 1d \
    --timezone Asia/Kolkata
  ```

> [!NOTE]
> **Phase 2C Scope Boundary**:
> - Phase 2C uses local historical files only. Live Zerodha historical-data retrieval remains deferred.
> - No live network access, order execution, indicators, or trading strategies are implemented.

---

## Phase 3 — Quantitative Analysis & Indicator Engine

Phase 3 implements a deterministic, provider-independent quantitative evidence engine that consumes trusted Phase 2 historical data and calculates 21 canonical technical features without making subjective trading decisions.

```text
                 Phase 2
        Canonical Historical Data
                    │
                    ▼
        HistoricalDataRepository
                    │
                    ▼
             Quant Engine
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      Trend      Momentum     Volume
        │           │           │
        ├───────────┼───────────┤
        ▼           ▼           ▼
    Volatility   Structure   Relative Strength
        │           │           │
        └───────────┼───────────┘
                    ▼
          Indicator / Feature Set
                    │
                    ▼
          Quantitative Evidence
         (Auditable Provenance)
                    │
                    ▼
             Phase 4 Input
```

### Core Architecture & Invariants

- **Evidence, Not Signals**: Phase 3 outputs purely factual quantitative metrics (`IndicatorSeries`, `IndicatorValue`). Zero `BUY`/`SELL`/`HOLD`/`WAIT` decisions, zero trading rules, zero composite quant scoring.
- **Strict Anti-Lookahead Guarantee**: Calculation at timestamp $T$ strictly observes data available at or before $T$. Verified via prefix vs. full series regression tests.
- **Zero Silent Imputation**: If insufficient data is provided (e.g. 50 bars for 200 SMA), the engine returns `status = INSUFFICIENT_DATA` and `value = None`. No forward-filling or manufactured numbers.
- **Fail-Closed Validation**: Incoming candle series must be strictly ascending, non-empty, UTC timezone-aware, uniform in timeframe/symbol/exchange, and free from NaN/Inf.
- **Zero-Denominator Safety**:
  - `rvol`: If $\text{VolSMA} == 0 \implies \text{status} = \text{INVALID}, \text{value} = \text{None}$ (for both $0/0$ and $\text{pos}/0$).
  - `volume_change`: If $V_{t-1} == 0 \implies \text{status} = \text{INVALID}, \text{value} = \text{None}$.
- **Bollinger Bands Precedence**:
  - $\text{Middle} \le 0 \implies \text{INVALID}, \text{value} = \text{None}$.
  - Else if $\sigma == 0$ (positive middle, zero variance) $\implies \text{VALID}, \text{bandwidth} = 0.0, \text{percent\_b} = 0.5$.
  - Else $\implies$ standard Bollinger calculation.
- **Deterministic Provenance**: `IndicatorProvenance` is strictly deterministic (no runtime timestamps). Runtime execution metadata is decoupled into `QuantRunContext`.
- **Relative Strength Exact Alignment**: Asset and benchmark timestamps must match exactly in UTC. No interpolation or forward fill; missing benchmark timestamps yield `INSUFFICIENT_DATA`.

### 21 Canonical Registered Indicators

| Group | Indicator Name | Class | Canonical Identifier | Default Lookback |
| :--- | :--- | :--- | :--- | :--- |
| **Trend** | Simple Moving Average | `SMAIndicator` | `sma` | 20 |
| | Exponential Moving Average | `EMAIndicator` | `ema` | 20 |
| | Price vs SMA Ratio | `PriceVsSMAIndicator` | `price_vs_sma` | 20 |
| | SMA Slope | `SMASlopeIndicator` | `sma_slope` | 20 (lag 1) |
| | EMA Slope | `EMASlopeIndicator` | `ema_slope` | 20 (lag 1) |
| **Momentum** | Rate of Change | `ROCIndicator` | `roc` | 14 |
| | Relative Strength Index | `RSIIndicator` | `rsi` | 14 (Wilder) |
| | Moving Avg Convergence Divergence | `MACDIndicator` | `macd` | 12, 26, 9 |
| **Volume** | Volume SMA | `VolumeSMAIndicator` | `volume_sma` | 20 |
| | Relative Volume | `RVOLIndicator` | `rvol` | 20 |
| | Volume Change (%) | `VolumeChangeIndicator` | `volume_change` | 1 |
| | On-Balance Volume | `OBVIndicator` | `obv` | Cumulative |
| **Volatility** | True Range | `TrueRangeIndicator` | `true_range` | 1 |
| | Average True Range | `ATRIndicator` | `atr` | 14 (Wilder) |
| | Normalized ATR (NATR %) | `NATRIndicator` | `natr` | 14 |
| | Rolling Sample Std Deviation | `RollingStdDevIndicator` | `rolling_std` | 20 ($N-1$) |
| | Bollinger Bands & Bandwidth | `BollingerBandsIndicator` | `bollinger_bands` | 20 (2.0 std) |
| **Structure** | Rolling High | `RollingHighIndicator` | `rolling_high` | 20 |
| | Rolling Low | `RollingLowIndicator` | `rolling_low` | 20 |
| | Breakout & Distance Features | `StructureBreakoutIndicator` | `structure_breakout_distance` | 20 |
| **Relative Strength** | Relative Strength vs Benchmark | `RelativeStrengthIndicator` | `relative_strength` | 20 |

### Scaling Benchmarks
Informational performance benchmarks are executed via:
```bash
python -m pytest -m benchmark -s
```
Normal `pytest` excludes benchmark runs by default to maintain fast sub-second CI validation.

---

## Current Status

- [x] **Phase 1: Bootstrap & Security** (Security foundation, centralized settings, SimulatedBroker, CI, secrets scanning)
- [x] **Phase 2A: Canonical Market Data Foundation** (Canonical models, Pydantic v2 validation, gap/staleness detection, MockMarketDataProvider, Zerodha boundary)
- [x] **Phase 2B: Historical Market Data & Storage** (Parquet store, idempotent merging, local provider, query repository, Zerodha historical boundary)
- [x] **Phase 2C: Historical Data Ingestion & Dataset Management** (CSV/Parquet ingestion, atomic persistence, deduplication, conflict detection, CLI, coverage reports)
- [x] **Phase 3: Quantitative Analysis & Indicator Engine** (Deterministic quant engine, 21 registered indicators, auditable provenance, zero-denominator safety, anti-lookahead guarantees, decoupled scaling benchmarks)
- [ ] *Future Phases*: Strategy formulation, Risk rules, Paper trading, Live trading.


