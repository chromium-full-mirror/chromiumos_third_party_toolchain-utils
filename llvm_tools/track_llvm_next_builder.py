# Copyright 2026 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tracks recent llvm-next builder invocations.

This script prints the status of the N most recent builder invocations, and
fails if all of them fail. The intent is for Chrotomation to run this regularly,
so the team can be alerted if these builders are consistently failing.
"""

import argparse
import json
import logging
import sys

from llvm_tools import bb_add
from llvm_tools import cros_cls
from llvm_tools import llvm_next


BUILDER_NICKNAMES: dict[str, str] = {
    "asan": "chromeos/staging/staging-amd64-generic-asan",
    "msan-fuzzer": "chromeos/staging/staging-amd64-generic-msan-fuzzer",
    "ubsan": "chromeos/staging/staging-amd64-generic-ubsan",
    "sdk": "chromeos/staging/staging-build-chromiumos-sdk",
}


def resolve_builder_name(name_or_nickname: str) -> str:
    """Resolves a builder nickname or full builder name to its full form."""
    if name_or_nickname in BUILDER_NICKNAMES:
        return BUILDER_NICKNAMES[name_or_nickname]
    if name_or_nickname in bb_add.DEFAULT_LLVM_NEXT_BUILDERS:
        return name_or_nickname
    valid = sorted(
        (*BUILDER_NICKNAMES.keys(), *bb_add.DEFAULT_LLVM_NEXT_BUILDERS)
    )
    raise argparse.ArgumentTypeError(
        f"Unknown builder {name_or_nickname!r}. Valid options: {valid}"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-n",
        "--number-to-check",
        type=int,
        default=5,
        help="Number of builds to check (default: %(default)s)",
    )
    parser.add_argument(
        "-b",
        "--builder",
        action="append",
        dest="builders",
        type=resolve_builder_name,
        help="""
        Builder to monitor, either a nickname (e.g., 'sdk') or full name
        (e.g., 'chromeos/staging/staging-build-chromiumos-sdk'). May be
        specified multiple times (default: 'sdk').
        """,
    )
    opts = parser.parse_args(argv)
    if not opts.builders:
        opts.builders = [BUILDER_NICKNAMES["sdk"]]
    return opts


def check_builder(builder: str, number_to_check: int) -> bool:
    """Checks the N most recent runs of `builder`; returns True if healthy."""
    ls_args: list[str] = []
    project, bucket, builder_name = builder.split("/", 2)

    # `ls` will show running/started builds, which we want to ignore.
    #
    # We could alternatively e.g., request `number_to_check*2` builds and
    # filter the running ones out ourselves, but the number of running builds is
    # _technically_ not bounded. Prefer `or`ing a handful of `-predicate`s
    # instead.
    for status in cros_cls.BuilderStatus:
        if status.is_running:
            continue
        predicate = json.dumps(
            {
                "builder": {
                    "project": project,
                    "bucket": bucket,
                    "builder": builder_name,
                },
                "tags": [
                    {"key": "toolchain", "value": "non-cq-llvm-next-testing"}
                ],
                "status": status.value,
            }
        )
        ls_args += ("-predicate", predicate)
    ls_args += ("-n", str(number_to_check))

    logging.info(
        "Running `bb ls` for %s - this may take a few dozen seconds...",
        builder,
    )
    builds = cros_cls.fetch_bb_ls_info(ls_args=ls_args)
    if not builds:
        logging.warning("No builds found for %s.", builder)
        return False

    for build in builds:
        logging.info(
            "[%s] Status: %s, Time: %s, Link: %s",
            builder_name,
            build.status,
            build.create_time,
            cros_cls.builder_url(build.build_id),
        )

    if all(b.status.is_failure for b in builds):
        logging.error(
            "All %d most recent runs of %s failed",
            len(builds),
            builder,
        )
        return False

    logging.info("Success: Not all recent builds of %s failed.", builder)
    return True


def main(argv: list[str]) -> None:
    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.INFO,
    )
    opts = parse_args(argv)

    if not llvm_next.LLVM_NEXT_MANIFEST_CL:
        logging.info("No llvm-next manifest CL is registered; exiting cleanly.")
        return

    all_healthy = True
    for builder in opts.builders:
        if not check_builder(builder, opts.number_to_check):
            all_healthy = False

    if not all_healthy:
        logging.error("Not all builders are healthy; exiting uncleanly.")
        sys.exit(1)
