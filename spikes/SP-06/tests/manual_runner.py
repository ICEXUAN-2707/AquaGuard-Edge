"""Small command-line harness for the human SP-06 walkthrough."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spike import (  # noqa: E402
    apply_transition,
    claim_one,
    connect,
    initialize,
    process_one,
    recover_sending,
)


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "manual_cases.json"


def _load_case(name: str) -> dict:
    cases = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    try:
        return cases[name]
    except KeyError as exc:
        raise SystemExit(f"Unknown case {name!r}; see {DATA_PATH}") from exc


def _inspect(db_path: str) -> None:
    with connect(db_path) as db:
        for table in ("events", "transitions", "outbox"):
            rows = [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            print(f"[{table}] {json.dumps(rows, ensure_ascii=False, indent=2)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create tables; does not erase existing data")
    init_parser.add_argument("--db", required=True)

    submit_parser = subparsers.add_parser("submit", help="apply one JSON dataset case")
    submit_parser.add_argument("--db", required=True)
    submit_parser.add_argument("--case", required=True)

    worker_parser = subparsers.add_parser("worker", help="send one row through a Mock Cloud result")
    worker_parser.add_argument("--db", required=True)
    worker_parser.add_argument("--outcome", choices=("accepted", "retry", "failed"), required=True)
    worker_parser.add_argument("--business-receipt", action="store_true")

    for command in ("claim", "recover", "inspect"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--db", required=True)

    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.db)
            print(f"initialized (existing rows preserved): {args.db}")
        elif args.command == "submit":
            result = apply_transition(args.db, **_load_case(args.case))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "worker":
            outcome = args.outcome.upper()

            def mock_sender(message: dict) -> dict:
                if outcome == "ACCEPTED":
                    result = {
                        "status": outcome,
                        "transport_receipt": {
                            "provider": "manual_mock",
                            "receipt_id": f"transport-{message['message_id']}-{message['attempts']}",
                        },
                    }
                    if args.business_receipt:
                        result["business_receipt"] = {
                            "provider": "manual_mock_consumer",
                            "receipt_id": f"business-{message['message_id']}",
                        }
                    return result
                return {
                    "status": "RETRY_WAIT" if outcome == "RETRY" else "FAILED",
                    "error": f"manual mock outcome: {outcome}",
                }

            print(process_one(args.db, mock_sender) or "no eligible outbox row")
        elif args.command == "claim":
            print(json.dumps(claim_one(args.db), ensure_ascii=False, indent=2))
        elif args.command == "recover":
            print(f"recovered rows: {recover_sending(args.db)}")
        elif args.command == "inspect":
            _inspect(args.db)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
