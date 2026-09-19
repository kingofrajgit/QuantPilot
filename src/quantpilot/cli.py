"""QuantPilot Command Line Interface (CLI)."""

import argparse
import sys
from datetime import datetime

from quantpilot.market_data.ingestion_models import IngestionFormat, IngestionRunStatus
from quantpilot.market_data.ingestion_service import HistoricalDataIngestionService
from quantpilot.market_data.models import Timeframe


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser for QuantPilot CLI."""
    parser = argparse.ArgumentParser(
        prog="quantpilot",
        description="QuantPilot quantitative trading research & decision support CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # `data` subcommands
    data_parser = subparsers.add_parser("data", help="Market data management commands")
    data_subparsers = data_parser.add_subparsers(dest="subcommand", help="Data commands")

    ingest_parser = data_subparsers.add_parser(
        "ingest", help="Ingest local historical market data file atomically"
    )
    ingest_parser.add_argument(
        "--source",
        required=True,
        help="Path to historical source file (relative to PROJECT_ROOT or absolute)",
    )
    ingest_parser.add_argument(
        "--format",
        required=True,
        choices=["csv", "parquet"],
        help="Format of source file (csv or parquet)",
    )
    ingest_parser.add_argument(
        "--symbol",
        required=True,
        help="Ticker symbol (e.g. RELIANCE)",
    )
    ingest_parser.add_argument(
        "--exchange",
        required=True,
        help="Exchange identifier (e.g. NSE)",
    )
    ingest_parser.add_argument(
        "--timeframe",
        required=True,
        help="Candle resolution (e.g. 1d, 1m, 5m, 15m, 1h)",
    )
    ingest_parser.add_argument(
        "--start",
        default=None,
        help="Optional ISO start timestamp for filtering (e.g. 2026-01-01T00:00:00Z)",
    )
    ingest_parser.add_argument(
        "--end",
        default=None,
        help="Optional ISO end timestamp for filtering (e.g. 2026-01-31T23:59:59Z)",
    )
    ingest_parser.add_argument(
        "--timezone",
        default=None,
        help="Source timezone for naive timestamps (e.g. Asia/Kolkata, UTC)",
    )

    return parser


def handle_data_ingest(args: argparse.Namespace) -> int:
    """Execute historical data ingestion from parsed CLI arguments."""
    start_dt = None
    if args.start:
        try:
            start_dt = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
        except ValueError as ex:
            print(f"Error: Invalid --start timestamp format: {ex}")
            return 1

    end_dt = None
    if args.end:
        try:
            end_dt = datetime.fromisoformat(args.end.replace("Z", "+00:00"))
        except ValueError as ex:
            print(f"Error: Invalid --end timestamp format: {ex}")
            return 1

    service = HistoricalDataIngestionService()
    summary = service.ingest(
        source_path=args.source,
        source_format=IngestionFormat(args.format),
        symbol=args.symbol,
        exchange=args.exchange,
        timeframe=Timeframe(args.timeframe),
        start_time=start_dt,
        end_time=end_dt,
        source_timezone=args.timezone,
    )

    # Format output table
    earliest_str = summary.earliest_timestamp.isoformat() if summary.earliest_timestamp else "N/A"
    latest_str = summary.latest_timestamp.isoformat() if summary.latest_timestamp else "N/A"

    print("\nHistorical Data Ingestion Summary")
    print("---------------------------------")
    print(f"Run ID:             {summary.run_id}")
    print(f"Symbol:             {summary.symbol}")
    print(f"Exchange:           {summary.exchange}")
    print(f"Timeframe:          {summary.timeframe.value}")
    print(f"Source:             {summary.source}")
    print(f"Format:             {summary.source_format.value}")
    print()
    print(f"Records Read:       {summary.records_read}")
    print(f"Records Valid:      {summary.records_valid}")
    print(f"Records Written:    {summary.records_written}")
    print(f"Records Skipped:    {summary.records_skipped}")
    print(f"Duplicates:         {summary.duplicates}")
    print(f"Conflicts:          {summary.conflicts}")
    print(f"Validation Errors:  {summary.validation_failures}")
    print()
    print(f"Earliest Timestamp: {earliest_str}")
    print(f"Latest Timestamp:   {latest_str}")
    print(f"Status:             {summary.status.value}")

    if summary.errors:
        print("\nErrors / Warnings:")
        for err in summary.errors[:10]:
            print(f" - {err}")
        if len(summary.errors) > 10:
            print(f" - ... and {len(summary.errors) - 10} more errors")

    return 0 if summary.status == IngestionRunStatus.SUCCESS else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.command == "data" and args.subcommand == "ingest":
        return handle_data_ingest(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
