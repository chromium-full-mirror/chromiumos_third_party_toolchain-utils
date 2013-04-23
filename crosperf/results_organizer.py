#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parse data from benchmark_runs for tabulator."""
import re


class ResultOrganizer(object):
  """Create a dict from benchmark_runs.

  The structure of the output dict is as follows:
  {"benchmark_1":[
    [{"key1":"v1", "key2":"v2"},{"key1":"v1", "key2","v2"}]
    #one label
    []
    #the other label
    ]
   "benchmark_2":
    [
    ]}.
  """
  key_filter = ["milliseconds_",
                "retval",
                "iterations",
                "ms_",
                "score_"]

  def __init__(self, benchmark_runs, labels, benchmarks=None):
    self.result = {}
    self.labels = []
    self.prog = re.compile(r"(\w+)\{(\d+)\}")
    self.benchmarks = benchmarks
    if not self.benchmarks:
      self.benchmarks = []
    for label in labels:
      self.labels.append(label.name)
    for benchmark_run in benchmark_runs:
      benchmark_name = benchmark_run.benchmark.name
      if benchmark_name not in self.result:
        self.result[benchmark_name] = []
        while len(self.result[benchmark_name]) < len(labels):
          self.result[benchmark_name].append([])
      label_index = self.labels.index(benchmark_run.label.name)
      cur_table = self.result[benchmark_name][label_index]
      index = benchmark_run.iteration - 1
      while index >= len(cur_table):
        cur_table.append({})
      cur_dict = cur_table[index]
      if not benchmark_run.result:
        continue
      benchmark = benchmark_run.benchmark
      key_filter_on = (benchmark.key_results_only and
                       "PyAutoPerfTest" in benchmark.name + benchmark.test_name
                       and "perf." not in benchmark.test_args)
      for test_key in benchmark_run.result.keyvals:
        if (key_filter_on and
            not any([key for key in self.key_filter if key in test_key])
           ):
          continue
        result_value = benchmark_run.result.keyvals[test_key]
        cur_dict[test_key] = result_value
    self._DuplicatePass()

  def _DuplicatePass(self):
    for bench, data in self.result.items():
      max_dup = self._GetMaxDup(data)
      if not max_dup:
        continue
      for label in data:
        index = data.index(label)
        data[index] = self._GetNonDupLabel(max_dup, label)
      self._AdjustIteration(max_dup, bench)

  def _GetMaxDup(self, data):
    """Find the maximum i inside ABCD{i}."""
    max_dup = 0
    for label in data:
      for run in label:
        for key in run:
          if re.match(self.prog, key):
            max_dup = max(max_dup,
                          int(re.search(self.prog, key).group(2)))
    return max_dup

  def _GetNonDupLabel(self, max_dup, label):
    """Create new list for the runs of the same label."""
    new_label = []
    for run in label:
      start_index = len(new_label)
      new_label.append(dict(run))
      for i in range(max_dup):
        new_label.append({})
      new_run = new_label[start_index]
      for key, value in new_run.items():
        if re.match(self.prog, key):
          new_key = re.search(self.prog, key).group(1)
          index = int(re.search(self.prog, key).group(2))
          new_label[start_index+index][new_key] = str(value)
          del new_run[key]
    return new_label

  def _AdjustIteration(self, max_dup, bench):
    """Adjust the interation numbers if the have keys like ABCD{i}."""
    for benchmark in self.benchmarks:
      if benchmark.name == bench:
        if not benchmark.iteration_adjusted:
          benchmark.iteration_adjusted = True
          benchmark.iterations *= (max_dup +1)
