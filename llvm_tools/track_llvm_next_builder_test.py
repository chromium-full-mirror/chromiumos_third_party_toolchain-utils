# Copyright 2026 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for track_llvm_next_builder.py."""

import argparse
import datetime
import unittest
from unittest import mock

from llvm_tools import bb_add
from llvm_tools import cros_cls
from llvm_tools import track_llvm_next_builder


class TestTrackLlvmNextBuilder(unittest.TestCase):
    """Tests for track_llvm_next_builder."""

    def test_resolve_builder_name_shorthand(self) -> None:
        self.assertEqual(
            track_llvm_next_builder.resolve_builder_name("asan"),
            "chromeos/staging/staging-amd64-generic-asan",
        )
        self.assertEqual(
            track_llvm_next_builder.resolve_builder_name("msan-fuzzer"),
            "chromeos/staging/staging-amd64-generic-msan-fuzzer",
        )
        self.assertEqual(
            track_llvm_next_builder.resolve_builder_name("ubsan"),
            "chromeos/staging/staging-amd64-generic-ubsan",
        )
        self.assertEqual(
            track_llvm_next_builder.resolve_builder_name("sdk"),
            "chromeos/staging/staging-build-chromiumos-sdk",
        )

    def test_resolve_builder_name_full_name(self) -> None:
        for full_builder in bb_add.DEFAULT_LLVM_NEXT_BUILDERS:
            with self.subTest(builder=full_builder):
                self.assertEqual(
                    track_llvm_next_builder.resolve_builder_name(full_builder),
                    full_builder,
                )

    def test_resolve_builder_name_invalid(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            track_llvm_next_builder.resolve_builder_name("non-existent-builder")

    @mock.patch.object(cros_cls, "fetch_bb_ls_info", autospec=True)
    def test_check_builder_returns_false_when_no_builds_found(
        self, mock_fetch: mock.MagicMock
    ) -> None:
        mock_fetch.return_value = []
        self.assertFalse(
            track_llvm_next_builder.check_builder(
                "chromeos/staging/staging-build-chromiumos-sdk", 5
            )
        )

    @mock.patch.object(cros_cls, "fetch_bb_ls_info", autospec=True)
    def test_check_builder_returns_false_when_all_builds_failed(
        self, mock_fetch: mock.MagicMock
    ) -> None:
        now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        mock_fetch.return_value = [
            cros_cls.BbLsInfo(
                build_id=cros_cls.BuildID(100),
                builder_name="staging-build-chromiumos-sdk",
                status=cros_cls.BuilderStatus.FAILURE,
                create_time=now,
            ),
            cros_cls.BbLsInfo(
                build_id=cros_cls.BuildID(101),
                builder_name="staging-build-chromiumos-sdk",
                status=cros_cls.BuilderStatus.INFRA_FAILURE,
                create_time=now,
            ),
        ]
        self.assertFalse(
            track_llvm_next_builder.check_builder(
                "chromeos/staging/staging-build-chromiumos-sdk", 5
            )
        )

    @mock.patch.object(cros_cls, "fetch_bb_ls_info", autospec=True)
    def test_check_builder_returns_true_when_not_all_builds_failed(
        self, mock_fetch: mock.MagicMock
    ) -> None:
        now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        mock_fetch.return_value = [
            cros_cls.BbLsInfo(
                build_id=cros_cls.BuildID(100),
                builder_name="staging-build-chromiumos-sdk",
                status=cros_cls.BuilderStatus.FAILURE,
                create_time=now,
            ),
            cros_cls.BbLsInfo(
                build_id=cros_cls.BuildID(101),
                builder_name="staging-build-chromiumos-sdk",
                status=cros_cls.BuilderStatus.SUCCESS,
                create_time=now,
            ),
        ]
        self.assertTrue(
            track_llvm_next_builder.check_builder(
                "chromeos/staging/staging-build-chromiumos-sdk", 5
            )
        )
