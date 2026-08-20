#!/usr/bin/env python3
"""Keep the newest N release archives in dist/, delete the rest.

`dist/` is the one directory in this working tree that only ever grows: every
release leaves a SaaS and an Edition tarball behind, and this tree lives in
iCloud Drive — so 1.3 GB of superseded archives was being synced to Apple and
to every device on the account, forever.

Deleting them is safe in the one sense that matters: an archive is
reproducible. `git checkout <tag> && bash deploy/aws/build_aws_bundle.sh
<version>` rebuilds a byte-identical bundle, and the SHA-256 of every shipped
archive is recorded in the handoff ledger, so a rebuild can be proven to match
what was deployed. What is NOT reproducible — the ledger, the dumps, the
handoff — lives elsewhere and is never touched here.

Dry run by default; deletion needs --apply. Mirrors the production policy in
lightsail_ctl.sh prune-artifacts (keep 3).

    python3 backend/scripts/prune_dist.py            # show what would go
    python3 backend/scripts/prune_dist.py --apply    # actually delete
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

DIST = Path(__file__).resolve().parents[2] / "dist"
ARCHIVE = re.compile(r"^(?P<stem>.+?)-(?P<version>\d+(?:\.\d+)*)\.tar\.gz$")


def version_key(text: str) -> tuple:
    return tuple(int(part) for part in text.split("."))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=3, help="versions to keep (default 3)")
    parser.add_argument("--apply", action="store_true", help="delete instead of listing")
    args = parser.parse_args()

    if not DIST.is_dir():
        print(f"{DIST} does not exist — nothing to prune.")
        return 0
    if args.keep < 1:
        raise SystemExit("--keep must be at least 1")

    versions = set()
    by_version = defaultdict(list)
    for path in DIST.iterdir():
        match = ARCHIVE.match(path.name)
        if not match:
            continue
        version = match.group("version")
        versions.add(version)
        by_version[version].append(path)
        checksum = path.with_name(path.name + ".sha256")
        if checksum.is_file():
            by_version[version].append(checksum)

    if not versions:
        print(f"No release archives in {DIST}.")
        return 0

    ordered = sorted(versions, key=version_key, reverse=True)
    keep, drop = ordered[: args.keep], ordered[args.keep :]
    print(f"keeping {args.keep} newest: {', '.join(keep)}")
    if not drop:
        print("nothing superseded — dist/ is already within the policy.")
        return 0

    freed = 0
    for version in drop:
        for path in sorted(by_version[version]):
            freed += path.stat().st_size
            print(f"  {'delete' if args.apply else 'would delete'}  {path.name}")
            if args.apply:
                path.unlink()
    print(f"{'freed' if args.apply else 'would free'} {freed / 1e9:.2f} GB "
          f"across {len(drop)} superseded version(s)")
    if not args.apply:
        print("dry run — re-run with --apply to delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
