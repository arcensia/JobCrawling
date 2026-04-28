#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI 진입점 — 실제 로직은 adapters/sync/reaction.py 참고."""

if __name__ == "__main__":
    import argparse
    from adapters.sync.reaction import sync_once

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print("=== 리액션 동기화 시작 ===")
    sync_once(dry_run=args.dry_run)
