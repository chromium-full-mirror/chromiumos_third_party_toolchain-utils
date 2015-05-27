#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

"""The experiment runner module."""
import getpass
import os
import time

import afe_lock_machine

from utils import command_executer
from utils import logger
from utils.email_sender import EmailSender
from utils.file_utils import FileUtils

import config
from experiment_status import ExperimentStatus
from results_report import HTMLResultsReport
from results_report import TextResultsReport


class ExperimentRunner(object):
  """ExperimentRunner Class."""

  STATUS_TIME_DELAY = 30
  THREAD_MONITOR_DELAY = 2

  def __init__(self, experiment, log=None, cmd_exec=None):
    self._experiment = experiment
    self.l = log or logger.GetLogger(experiment.log_dir)
    self._ce = cmd_exec or command_executer.GetCommandExecuter(self.l)
    self._terminated = False
    if experiment.log_level != "verbose":
      self.STATUS_TIME_DELAY = 10

  def _GetMachineList(self):
    """Return a list of all requested machines.

    Create a list of all the requested machines, both global requests and
    label-specific requests, and return the list.
    """
    machines = self._experiment.remote
    for l in self._experiment.labels:
      if l.remote:
        machines += l.remote
    return machines

  def _LockAllMachines(self, experiment):
    """Attempt to globally lock all of the machines requested for run.

    This method will use the AFE server to globally lock all of the machines
    requested for this crosperf run, to prevent any other crosperf runs from
    being able to update/use the machines while this experiment is running.
    """
    lock_mgr = afe_lock_machine.AFELockManager(
        self._GetMachineList(),
        "",
        experiment.labels[0].chromeos_root,
        None,
        log=self.l,
    )
    for m in lock_mgr.machines:
      if not lock_mgr.MachineIsKnown(m):
        lock_mgr.AddLocalMachine(m)
    machine_states = lock_mgr.GetMachineStates("lock")
    lock_mgr.CheckMachineLocks(machine_states, "lock")
    lock_mgr.UpdateMachines(True)

  def _UnlockAllMachines(self, experiment):
    """Attempt to globally unlock all of the machines requested for run.

    The method will use the AFE server to globally unlock all of the machines
    requested for this crosperf run.
    """
    lock_mgr = afe_lock_machine.AFELockManager(
        self._GetMachineList(),
        "",
        experiment.labels[0].chromeos_root,
        None,
        log=self.l,
    )
    machine_states = lock_mgr.GetMachineStates("unlock")
    lock_mgr.CheckMachineLocks(machine_states, "unlock")
    lock_mgr.UpdateMachines(False)

  def _Run(self, experiment):
    try:
      self._LockAllMachines(experiment)
      status = ExperimentStatus(experiment)
      experiment.Run()
      last_status_time = 0
      last_status_string = ""
      try:
        if experiment.log_level != "verbose":
          self.l.LogStartDots()
        while not experiment.IsComplete():
          if last_status_time + self.STATUS_TIME_DELAY < time.time():
            last_status_time = time.time()
            border = "=============================="
            if experiment.log_level == "verbose":
              self.l.LogOutput(border)
              self.l.LogOutput(status.GetProgressString())
              self.l.LogOutput(status.GetStatusString())
              self.l.LogOutput(border)
            else:
              current_status_string = status.GetStatusString()
              if (current_status_string != last_status_string):
                self.l.LogEndDots()
                self.l.LogOutput(border)
                self.l.LogOutput(current_status_string)
                self.l.LogOutput(border)
                last_status_string = current_status_string
              else:
                self.l.LogAppendDot()
          time.sleep(self.THREAD_MONITOR_DELAY)
      except KeyboardInterrupt:
        self._terminated = True
        self.l.LogError("Ctrl-c pressed. Cleaning up...")
        experiment.Terminate()
    finally:
      self._UnlockAllMachines(experiment)

  def _PrintTable(self, experiment):
    self.l.LogOutput(TextResultsReport(experiment).GetReport())

  def _Email(self, experiment):
    # Only email by default if a new run was completed.
    send_mail = False
    for benchmark_run in experiment.benchmark_runs:
      if not benchmark_run.cache_hit:
        send_mail = True
        break
    if (not send_mail and not experiment.email_to
        or config.GetConfig("no_email")):
      return

    label_names = []
    for label in experiment.labels:
      label_names.append(label.name)
    subject = "%s: %s" % (experiment.name, " vs. ".join(label_names))

    text_report = TextResultsReport(experiment, True).GetReport()
    text_report += ("\nResults are stored in %s.\n" %
                    experiment.results_directory)
    text_report = "<pre style='font-size: 13px'>%s</pre>" % text_report
    html_report = HTMLResultsReport(experiment).GetReport()
    attachment = EmailSender.Attachment("report.html", html_report)
    email_to = [getpass.getuser()] + experiment.email_to
    EmailSender().SendEmail(email_to,
                            subject,
                            text_report,
                            attachments=[attachment],
                            msg_type="html")

  def _StoreResults (self, experiment):
    if self._terminated:
      return
    results_directory = experiment.results_directory
    FileUtils().RmDir(results_directory)
    FileUtils().MkDirP(results_directory)
    self.l.LogOutput("Storing experiment file in %s." % results_directory)
    experiment_file_path = os.path.join(results_directory,
                                        "experiment.exp")
    FileUtils().WriteFile(experiment_file_path, experiment.experiment_file)

    self.l.LogOutput("Storing results report in %s." % results_directory)
    results_table_path = os.path.join(results_directory, "results.html")
    report = HTMLResultsReport(experiment).GetReport()
    FileUtils().WriteFile(results_table_path, report)

    self.l.LogOutput("Storing email message body in %s." % results_directory)
    msg_file_path = os.path.join(results_directory, "msg_body.html")
    text_report = TextResultsReport(experiment, True).GetReport()
    text_report += ("\nResults are stored in %s.\n" %
                    experiment.results_directory)
    msg_body = "<pre style='font-size: 13px'>%s</pre>" % text_report
    FileUtils().WriteFile(msg_file_path, msg_body)

    self.l.LogOutput("Storing results of each benchmark run.")
    for benchmark_run in experiment.benchmark_runs:
      if benchmark_run.result:
        benchmark_run_name = filter(str.isalnum, benchmark_run.name)
        benchmark_run_path = os.path.join(results_directory,
                                          benchmark_run_name)
        benchmark_run.result.CopyResultsTo(benchmark_run_path)
        benchmark_run.result.CleanUp(benchmark_run.benchmark.rm_chroot_tmp)

  def Run(self):
    self._Run(self._experiment)
    self._PrintTable(self._experiment)
    if not self._terminated:
      self._StoreResults(self._experiment)
      self._Email(self._experiment)


class MockExperimentRunner(ExperimentRunner):
  """Mocked ExperimentRunner for testing."""

  def __init__(self, experiment):
    super(MockExperimentRunner, self).__init__(experiment)

  def _Run(self, experiment):
    self.l.LogOutput("Would run the following experiment: '%s'." %
                     experiment.name)

  def _PrintTable(self, experiment):
    self.l.LogOutput("Would print the experiment table.")

  def _Email(self, experiment):
    self.l.LogOutput("Would send result email.")

  def _StoreResults(self, experiment):
    self.l.LogOutput("Would store the results.")
