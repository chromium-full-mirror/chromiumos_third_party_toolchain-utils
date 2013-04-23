#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from utils import command_executer


class SuiteRunner(object):
  """ This defines the interface from crosperf to test script.
  """
  def __init__(self, logger_to_use=None):
    self._logger = logger_to_use
    self._ce = command_executer.GetCommandExecuter(self._logger)
    self._ct = command_executer.CommandTerminator()

  def Run(self, machine, label, benchmark, test_args):
    if benchmark.suite == "telemetry":
      return self.Telemetry_Run(machine, label, benchmark)
    else:
      return self.Pyauto_Run(machine, label, benchmark, test_args)

  def Pyauto_Run(self, machine, label, benchmark, test_args):
    """Run the run_remote_test."""

    options = ""
    if label.board:
      options += " --board=%s" % label.board
    if test_args:
      options += " %s" % test_args
    command = "rm -rf /usr/local/autotest/results/*"
    self._ce.CrosRunCommand(command, machine=machine, username="root",
                            chromeos_root=label.chromeos_root)
    command = ("./run_remote_tests.sh --remote=%s %s %s" %
               (machine, options, benchmark.test_name))
    return self._ce.ChrootRunCommand(label.chromeos_root,
                                     command,
                                     True,
                                     self._ct)

  def Telemetry_Run(self, machine, label, benchmark):
    if not os.path.isdir(label.chrome_src):
      self._logger.GetLogger().LogFatal("Cannot find chrome src dir to"
                                        "run telemetry.")
    rsa_key = os.path.join(label.chromeos_root,
        "src/scripts/mod_for_test_scripts/ssh_keys/testing_rsa")
    cmd = ("cd {0} && "
           "./tools/perf/run_multipage_benchmarks "
           "--browser=cros-chrome "
           "--output-format=csv "
           "--remote={1} "
           "--identity {2} "
           "{3} {4}".format(label.chrome_src, machine,
                            rsa_key,
                            benchmark.test_name,
                            benchmark.test_args))
    return self._ce.RunCommand(cmd, return_output=True,
                               print_to_console=False)

  def Terminate(self):
    self._ct.Terminate()


class MockSuiteRunner(object):
  def __init__(self):
    pass

  def Run(self, *args):
    return ["", "", 0]
