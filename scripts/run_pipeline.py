#!/usr/bin/env python3
"""Run the ChronoRoute TLC pipeline from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chronoroute_pipeline.tlc_source import check_tlc_file_available, list_supported_services, list_target_months


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ChronoRoute multi-service TLC pipeline.")
    month_group = parser.add_mutually_exclusive_group(required=True)
    month_group.add_argument("--month", help="Single target month, e.g. 2026-03")
    month_group.add_argument("--start-month", help="Start month for a range, e.g. 2026-01")
    parser.add_argument("--end-month", help="End month for a range, e.g. 2026-03")
    parser.add_argument("--services", nargs="+", default=list_supported_services(), choices=list_supported_services())
    parser.add_argument("--overwrite", action="store_true", help="Redownload bronze files if they already exist.")
    parser.add_argument("--validate-only", action="store_true", help="Run validation checks without ingesting or transforming.")
    parser.add_argument("--check-only", action="store_true", help="Only check TLC source availability.")
    return parser.parse_args()


def split_month(month: str) -> tuple[int, int]:
    year, month_num = month.split("-")
    return int(year), int(month_num)


def main() -> int:
    args = parse_args()
    months = [args.month] if args.month else list_target_months(args.start_month, args.end_month)
    statuses = []
    if not args.check_only:
        from chronoroute_pipeline.aggregate import generate_combined_service_metrics, generate_gold_for_service
        from chronoroute_pipeline.export import export_frontend_artifacts
        from chronoroute_pipeline.ingest import download_month
        from chronoroute_pipeline.transform import clean_month
        from chronoroute_pipeline.validate import validate_raw_month, validate_silver_month

    for month in months:
        year, month_num = split_month(month)
        for service in args.services:
            if args.check_only:
                available = check_tlc_file_available(service, year, month_num)
                statuses.append({"service_type": service, "month": month, "available": available})
                continue
            if args.validate_only:
                statuses.append(validate_raw_month(service, year, month_num))
                statuses.append(validate_silver_month(service, year, month_num))
                continue
            status = download_month(service, year, month_num, overwrite=args.overwrite)
            statuses.append(status)
            if status["status"] in {"downloaded", "skipped"}:
                statuses.append(validate_raw_month(service, year, month_num))
                statuses.append(clean_month(service, year, month_num))
                statuses.append(validate_silver_month(service, year, month_num))
                statuses.append(generate_gold_for_service(service, year, month_num))
        if not args.check_only and not args.validate_only:
            processed_services = [service for service in args.services if any(item.get("service_type") == service and item.get("month") == month for item in statuses)]
            statuses.append(generate_combined_service_metrics(month, processed_services))
    if not args.check_only and not args.validate_only:
        statuses.append(export_frontend_artifacts(months, args.services))
    for status in statuses:
        print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
