#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The experiment setting module."""

import os
import time

import afe_lock_machine

from utils import logger
from utils import misc

from benchmark_run import BenchmarkRun
from machine_manager import MachineManager
from machine_manager import MockMachineManager
import test_flag


class Experiment(object):
  """Class representing an Experiment to be run."""

  def __init__(self, name, remote, working_directory,
               chromeos_root, cache_conditions, labels, benchmarks,
               experiment_file, email_to, acquire_timeout, log_dir,
               log_level, share_cache, results_directory, locks_directory):
    self.name = name
    self.working_directory = working_directory
    self.remote = remote
    self.chromeos_root = chromeos_root
    self.cache_conditions = cache_conditions
    self.experiment_file = experiment_file
    self.email_to = email_to
    if not results_directory:
      self.results_directory = os.path.join(self.working_directory,
                                            self.name + "_results")
    else:
      self.results_directory = misc.CanonicalizePath(results_directory)
    self.log_dir = log_dir
    self.log_level = log_level
    self.labels = labels
    self.benchmarks = benchmarks
    self.num_complete = 0
    self.num_run_complete = 0
    self.share_cache = share_cache
    self.active_threads = None

    # We need one chromeos_root to run the benchmarks in, but it doesn't
    # matter where it is, unless the ABIs are different.
    if not chromeos_root:
      for label in self.labels:
        if label.chromeos_root:
          chromeos_root = label.chromeos_root
    if not chromeos_root:
      raise Exception("No chromeos_root given and could not determine one from "
                      "the image path.")

    # This is a local directory, where the machine manager will keep track of
    # which machines are available for which benchmark run.   The assumption is
    # that all of the machines have been globally locked for this experiment,
    # to keep other people/experiments from accessing them, but we still need
    # the local locks directory to keep two or more benchmark runs within the
    # same experiment from trying to use the same machine at the same time.
    local_locks_directory = os.path.join(self.working_directory,
                                         "local_locks")
    if test_flag.GetTestMode():
      self.machine_manager = MockMachineManager(chromeos_root, acquire_timeout,
                                                log_level, locks_directory)
    else:
      self.machine_manager = MachineManager(chromeos_root, acquire_timeout,
                                            log_level, local_locks_directory)
    self.l = logger.GetLogger(log_dir)

    for machine in remote:
      self.machine_manager.AddMachine(machine)
    for label in labels:
      self.machine_manager.ComputeCommonCheckSum(label)
      self.machine_manager.ComputeCommonCheckSumString(label)

    self.start_time = None
    self.benchmark_runs = self._GenerateBenchmarkRuns()

  def _GenerateBenchmarkRuns(self):
    """Generate benchmark runs from labels and benchmark defintions."""
    benchmark_runs = []
    for label in self.labels:
      for benchmark in self.benchmarks:
        for iteration in range(1, benchmark.iterations + 1):

          benchmark_run_name = "%s: %s (%s)" % (label.name, benchmark.name,
                                                iteration)
          full_name = "%s_%s_%s" % (label.name, benchmark.name, iteration)
          logger_to_use = logger.Logger(self.log_dir,
                                        "run.%s" % (full_name),
                                        True)
          benchmark_run = BenchmarkRun(benchmark_run_name,
                                       benchmark,
                                       label,
                                       iteration,
                                       self.cache_conditions,
                                       self.machine_manager,
                                       logger_to_use,
                                       self.log_level,
                                       self.share_cache)

          benchmark_runs.append(benchmark_run)
    return benchmark_runs

  def Build(self):
    pass

  def Terminate(self):
    for t in self.benchmark_runs:
      if t.isAlive():
        self.l.LogError("Terminating run: '%s'." % t.name)
        t.Terminate()

  def IsComplete(self):
    if self.active_threads:
      for t in self.active_threads:
        if t.isAlive():
          t.join(0)
        if not t.isAlive():
          self.num_complete += 1
          if not t.cache_hit:
            self.num_run_complete += 1
          self.active_threads.remove(t)
      return False
    return True

  def Run(self):
    self.start_time = time.time()
    self.active_threads = []
    for benchmark_run in self.benchmark_runs:
      # Set threads to daemon so program exits when ctrl-c is pressed.
      benchmark_run.daemon = True
      benchmark_run.start()
      self.active_threads.append(benchmark_run)

  def SetCacheConditions(self, cache_conditions):
    for benchmark_run in self.benchmark_runs:
      benchmark_run.SetCacheConditions(cache_conditions)

  def Cleanup(self):
    """Make sure all machines are unlocked."""
    all_machines = self.remote
    for l in self.labels:
      all_machines += l.remote
    lock_mgr = afe_lock_machine.AFELockManager(all_machines, "",
                                               self.labels[0].chromeos_root,
                                               None)
    machine_states = lock_mgr.GetMachineStates("unlock")
    for k, state in machine_states.iteritems():
      if state["locked"]:
        lock_mgr.UpdateLockInAFE(False, k)
