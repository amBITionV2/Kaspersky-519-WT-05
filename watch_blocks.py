import argparse
import sys
import time
from typing import Optional

from app import create_app
from extensions import db
from models import Block, Statement

try:
    from web3_service import get_web3
except Exception:  # pragma: no cover
    get_web3 = lambda: None  # type: ignore


def _print_history() -> int:
    """Print existing blocks with timestamps, return latest index or -1."""
    count = db.session.query(Block).count()
    if count == 0:
        print("[internal] No blocks yet.")
        return -1
    print(f"[internal] Existing blocks: {count}")
    for blk in db.session.query(Block).order_by(Block.index.asc()).all():
        stmt_count = len(blk.statements)
        ts = blk.created_at.strftime('%Y-%m-%d %H:%M:%S') if blk.created_at else 'n/a'
        print(
            f"  - idx={blk.index} time={ts} hash={blk.hash[:12]}... prev={str(blk.prev_hash)[:12]}... statements={stmt_count}"
        )
    latest = db.session.query(Block).order_by(Block.index.desc()).limit(1).one()
    return latest.index


def watch_internal(interval: float) -> None:
    app = create_app()
    with app.app_context():
        print("[watch] Watching internal app blocks (DB) ...", flush=True)
        last_index: Optional[int] = _print_history()
        while True:
            try:
                # show unsealed statements count (helps demos)
                unsealed = db.session.query(Statement).filter(Statement.block_id.is_(None)).count()
                print(f"[internal] Unsealed statements: {unsealed}", flush=True)
                latest: Optional[Block] = (
                    db.session.query(Block).order_by(Block.index.desc()).limit(1).one_or_none()
                )
                if latest is not None and (last_index is None or latest.index != last_index):
                    count = db.session.query(Block).count()
                    stmt_count = len(latest.statements)
                    ts = latest.created_at.strftime('%Y-%m-%d %H:%M:%S') if latest.created_at else 'n/a'
                    print(f"[internal] New block idx={latest.index} time={ts} hash={latest.hash[:12]}... prev={str(latest.prev_hash)[:12]}... statements={stmt_count} total_blocks={count}", flush=True)
                    last_index = latest.index
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[watch] Stopped.")
                return
            except Exception as e:
                print(f"[watch] Error: {e}", file=sys.stderr)
                time.sleep(max(1.0, interval))


def watch_core(interval: float) -> None:
    app = create_app()
    with app.app_context():
        w3 = get_web3()
        if w3 is None:
            print("[core] Web3 not configured. Set ETH_RPC_URL.", file=sys.stderr)
            return
        print("[watch] Watching Core blockchain (polling latest block) ...", flush=True)
        last_block: Optional[int] = None
        while True:
            try:
                number = w3.eth.block_number
                if last_block is None:
                    last_block = number
                    print(f"[core] Current block: {number}", flush=True)
                elif number > last_block:
                    for n in range(last_block + 1, number + 1):
                        try:
                            blk = w3.eth.get_block(n)
                            print(
                                f"[core] New block #{blk.number} hash={blk.hash.hex()[:14]}... txs={len(blk.transactions)}",
                                flush=True,
                            )
                        except Exception:
                            print(f"[core] New block #{n}", flush=True)
                    last_block = number
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[watch] Stopped.")
                return
            except Exception as e:
                print(f"[watch] Error: {e}", file=sys.stderr)
                time.sleep(max(1.0, interval))


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch blocks: internal DB or Core chain")
    parser.add_argument(
        "--source",
        choices=["internal", "core"],
        default="internal",
        help="internal (app DB) or core (Core blockchain via ETH_RPC_URL)",
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval seconds")
    args = parser.parse_args()

    if args.source == "internal":
        watch_internal(args.interval)
    else:
        watch_core(args.interval)


if __name__ == "__main__":
    main()
