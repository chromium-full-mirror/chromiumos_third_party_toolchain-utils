#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testing of benchmark_run."""

import unittest

from utils import logger

from suite_runner import MockSuiteRunner
from benchmark_run import MockBenchmarkRun
from label import MockLabel
from benchmark import Benchmark
from machine_manager import MockMachineManager
from results_cache import MockResultsCache


class BenchmarkRunTest(unittest.TestCase):
  def testDryRun(self):
    my_label = MockLabel("test1", "image1", "/tmp/test_benchmark_run",
                         "x86-alex", "chromeos-alex1",
                         image_args="",
                         image_md5sum="",
                         cache_dir="")
    m = MockMachineManager("/tmp/chromeos_root", 0)
    m.AddMachine("chromeos-alex1")
    bench = Benchmark("PageCyler",
                      "Pyautoperf",
                      "",
                      1,
                      0.2,
                      False,
                      False,
                      "")
    b = MockBenchmarkRun("test run",
                         bench,
                         my_label,
                         1,
                         [],
                         m,
                         logger.GetLogger(),
                         "")
    b.cache = MockResultsCache()
    b.autotest_runner = MockAutotestRunner()
    b.start()


if __name__ == "__main__":
  unittest.main()
