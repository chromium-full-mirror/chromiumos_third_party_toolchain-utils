#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Benchmark(object):
  """Class representing a benchmark to be run.

  Contains details of the benchmark suite, arguments to pass to the suite,
  iterations to run the benchmark suite and so on. Note that the benchmark name
  can be different to the test suite name. For example, you may want to have
  two different benchmarks which run the same test_name with different
  arguments.
  """

  def __init__(self, name, test_name, test_args, iterations,
               outlier_range, key_results_only, rm_chroot_tmp, perf_args,
               suite="pyauto"):
    self.name = name
    #For telemetry, this is the benchmark name.
    self.test_name = test_name
    #For telemetry, this is the data.
    self.test_args = test_args
    self.iterations = iterations
    self.outlier_range = outlier_range
    self.perf_args = perf_args
    self.key_results_only = key_results_only
    self.rm_chroot_tmp = rm_chroot_tmp
    self.iteration_adjusted = False
    self.suite = suite
