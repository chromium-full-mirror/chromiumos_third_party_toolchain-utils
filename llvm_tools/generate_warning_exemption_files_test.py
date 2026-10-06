# Copyright 2025 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for generate_warning_exemption_files."""

import argparse
import textwrap
from unittest import mock

# Rename this so the lines in this test aren't all super-long
from llvm_tools import cros_cls
from llvm_tools import generate_warning_exemption_files as gen
from llvm_tools import test_helpers
from llvm_tools import warning_exemption
import yaml  # pylint: disable=import-error


class Test(test_helpers.TempDirTestCase):
    """Tests for generate_warning_exemption_files."""

    ### Below are essentially Go-lden file tests.

    def test_go_file_creation_works_with_no_warnings(self) -> None:
        actual = gen.create_go_file(
            llvm_revision=123,
            per_package_warnings={},
        )
        fname = "warningSuppressionsForLLVM_r123"
        expected = gen.GO_COPYRIGHT_HEADER + textwrap.dedent(
            f"""\

            package main

            func {fname}(packageNameAndCategory string) []string {{
                return nil
            }}
            """
        )
        self.assertEqual(expected, actual)

    def test_go_file_creation_works_with_a_few_warnings(self) -> None:
        amd64_generic = warning_exemption.Builder(
            name="amd64-generic", url="https://amd64-generic-url"
        )
        brya = warning_exemption.Builder(name="brya", url="https://brya-url")
        dog_pkg = warning_exemption.Package(
            category="dog",
            package_name="pkg",
        )
        actual = gen.create_go_file(
            llvm_revision=321,
            per_package_warnings={
                warning_exemption.Package(
                    category="cat",
                    package_name="pkg",
                ): (
                    warning_exemption.FatalWarningGroup(
                        warning_names={"bar", "foo"},
                        warning_lines=set(),
                    ),
                    {amd64_generic, brya},
                ),
                dog_pkg: (
                    warning_exemption.FatalWarningGroup(
                        warning_names={"baz"},
                        warning_lines=set(),
                    ),
                    {brya},
                ),
                warning_exemption.Package(
                    category="snek",
                    package_name="pkg",
                ): (
                    warning_exemption.FatalWarningGroup(
                        warning_names={"baz"},
                        warning_lines=set(),
                    ),
                    set(),
                ),
            },
            permanent_exemptions={
                dog_pkg: (
                    "Dog is deprecated; see "
                    "https://chromium-review.googlesource.com/c/1234."
                )
            },
        )
        fname = "warningSuppressionsForLLVM_r321"
        expected = gen.GO_COPYRIGHT_HEADER + textwrap.dedent(
            f"""\

            package main

            func {fname}(packageNameAndCategory string) []string {{
                switch packageNameAndCategory {{
                // Observed and suppressed on 2 builders during testing.
                // e.g., amd64-generic: https://amd64-generic-url.
                case "cat/pkg":
                    return []string{{ "-Wno-bar", "-Wno-foo" }}
                // Observed and suppressed on 1 builder during testing.
                // e.g., brya: https://brya-url.
                // Permanent suppression: Dog is deprecated; see
                // https://chromium-review.googlesource.com/c/1234.
                case "dog/pkg":
                    return []string{{ "-Wno-baz" }}
                // (No builder links were available for these exemptions).
                case "snek/pkg":
                    return []string{{ "-Wno-baz" }}
                default:
                    return nil
                }}
            }}
            """
        )
        self.assertEqual(expected, actual)

    def test_yaml_file_generation(self) -> None:
        amd64_generic = warning_exemption.Builder(
            name="amd64-generic",
            url="https://amd64-generic-url",
        )
        file_name = "foo.go"
        ignored_pkg = warning_exemption.Package("dead", "pkg")
        yaml_str = gen.create_yaml_file(
            file_name,
            per_package_warnings={
                warning_exemption.Package(
                    category="foo",
                    package_name="bar",
                ): (
                    warning_exemption.FatalWarningGroup(
                        warning_names={"foo", "bar"},
                        warning_lines={"Oh no [-Wfoo]", "Oh dear [-Wbar]"},
                    ),
                    {amd64_generic},
                ),
                ignored_pkg: (
                    warning_exemption.FatalWarningGroup(
                        warning_names={"dead-warn"},
                        warning_lines={"Ignored [-Wdead-warn]"},
                    ),
                    {amd64_generic},
                ),
            },
            permanent_exemptions={ignored_pkg: "Dead package (b/999)."},
        )

        print(yaml_str)
        per_package_warnings = [
            warning_exemption.YamlPackageWarnings(
                package=warning_exemption.Package("foo", "bar"),
                warning_lines=[
                    "Oh dear [-Wbar]",
                    "Oh no [-Wfoo]",
                ],
                warning_names=["bar", "foo"],
                observed_on=[amd64_generic],
            ),
        ]

        self.assertEqual(
            warning_exemption.YamlFile.from_yaml(yaml.safe_load(yaml_str)),
            warning_exemption.YamlFile(
                exemption_go_file_name=file_name,
                severe_warnings=["bar", "foo"],
                per_package_warnings=per_package_warnings,
                frozen_per_package_warnings=per_package_warnings,
            ),
        )

    def test_warning_path_canonicalization_works(self) -> None:
        result = gen.canonicalize_warning_lines(
            (
                "/build/brya/foo.cc:12:34: error: don't do this [-Wfoo2]",
                "/build/trogdor/foo.cc:12:34: error: don't do this [-Wfoo2]",
                "/path/to/foo.cc:12:34: error: don't do this [-Wfoo1]",
            )
        )
        expected_output = (
            "/build/BOARD/foo.cc:12:34: error: don't do this [-Wfoo2]",
            "/path/to/foo.cc:12:34: error: don't do this [-Wfoo1]",
        )
        self.assertEqual(result, sorted(expected_output))

    @mock.patch.object(
        cros_cls.CQBoardBuilderOutput, "fetch_many", autospec=True
    )
    @mock.patch.object(
        cros_cls, "fetch_cq_orchestrator_or_board_builder", autospec=True
    )
    def test_resolve_builder_artifacts_when_builders_lack_artifacts(
        self, mock_fetch: mock.Mock, mock_fetch_many: mock.Mock
    ) -> None:
        mock_fetch.side_effect = [
            (
                "staging-amd64-generic-asan",
                cros_cls.CQBoardBuilderOutput(
                    status=cros_cls.BuilderStatus.SUCCESS,
                    artifacts_link="gs://chromeos-image-archive/asan-artifacts",
                ),
            ),
            (
                "staging-build-chromiumos-sdk",
                cros_cls.CQBoardBuilderOutput(
                    status=cros_cls.BuilderStatus.SUCCESS,
                    artifacts_link=None,
                ),
            ),
            (
                "cq-orchestrator",
                cros_cls.CQOrchestratorOutput(
                    status=cros_cls.BuilderStatus.SUCCESS,
                    child_builders={"brya-cq": 101, "betty-cq": 102},
                ),
            ),
        ]
        mock_fetch_many.return_value = [
            cros_cls.CQBoardBuilderOutput(
                status=cros_cls.BuilderStatus.SUCCESS,
                artifacts_link=None,
            ),
            cros_cls.CQBoardBuilderOutput(
                status=cros_cls.BuilderStatus.SUCCESS,
                artifacts_link="gs://chromeos-image-archive/brya-artifacts",
            ),
        ]
        results = gen.resolve_builder_artifacts([1, 2, 3])
        self.assertEqual(
            results,
            [
                (
                    warning_exemption.Builder(
                        name="staging-amd64-generic-asan",
                        url="https://ci.chromium.org/b/1",
                    ),
                    "gs://chromeos-image-archive/asan-artifacts",
                ),
                (
                    warning_exemption.Builder(
                        name="brya-cq",
                        url="https://ci.chromium.org/b/101",
                    ),
                    "gs://chromeos-image-archive/brya-artifacts",
                ),
            ],
        )

    @mock.patch.object(gen, "resolve_builder_artifacts", autospec=True)
    def test_cmd_builders_raises_when_no_artifacts(
        self, mock_resolve: mock.Mock
    ) -> None:
        mock_resolve.return_value = []
        opts = argparse.Namespace(builder_id=[123])
        with self.assertRaisesRegex(
            ValueError, "No artifacts found across all given builders"
        ):
            gen.cmd_builders(opts)
