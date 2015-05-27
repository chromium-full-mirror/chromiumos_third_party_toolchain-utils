#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import image_chromeos
import math
import os.path
import re
import sys
import threading
import time


from utils import command_executer
from utils import logger
from utils import misc
from utils.file_utils import FileUtils

from image_checksummer import ImageChecksummer

CHECKSUM_FILE = "/usr/local/osimage_checksum_file"

class NonMatchingMachines(Exception):
  pass

class MissingLocksDirectory(Exception):
    """Raised when cannot find/access the machine locks directory."""

class CrosMachine(object):
  def __init__(self, name, chromeos_root, log_level, cmd_exec=None):
    self.name = name
    self.image = None
    self.checksum = None
    self.locked = False
    self.released_time = time.time()
    self.test_run = None
    self.chromeos_root = chromeos_root
    self.log_level = log_level
    self.ce = cmd_exec or command_executer.GetCommandExecuter(
        log_level=self.log_level)
    self.SetUpChecksumInfo()

  def SetUpChecksumInfo(self):
    if not self.IsReachable():
      self.machine_checksum = None
      return
    self._GetMemoryInfo()
    self._GetCPUInfo()
    self._ComputeMachineChecksumString()
    self._GetMachineID()
    self.machine_checksum = self._GetMD5Checksum(self.checksum_string)
    self.machine_id_checksum = self._GetMD5Checksum(self.machine_id)

  def IsReachable(self):
    command = "ls"
    ret = self.ce.CrosRunCommand(command,
                                 machine=self.name,
                                 chromeos_root=self.chromeos_root)
    if ret:
      return False
    return True

  def _ParseMemoryInfo(self):
    line = self.meminfo.splitlines()[0]
    usable_kbytes = int(line.split()[1])
    # This code is from src/third_party/test/files/client/bin/base_utils.py
    # usable_kbytes is system's usable DRAM in kbytes,
    #   as reported by memtotal() from device /proc/meminfo memtotal
    #   after Linux deducts 1.5% to 9.5% for system table overhead
    # Undo the unknown actual deduction by rounding up
    #   to next small multiple of a big power-of-two
    #   eg  12GB - 5.1% gets rounded back up to 12GB
    mindeduct = 0.005  # 0.5 percent
    maxdeduct = 0.095  # 9.5 percent
    # deduction range 1.5% .. 9.5% supports physical mem sizes
    #    6GB .. 12GB in steps of .5GB
    #   12GB .. 24GB in steps of 1 GB
    #   24GB .. 48GB in steps of 2 GB ...
    # Finer granularity in physical mem sizes would require
    #   tighter spread between min and max possible deductions

    # increase mem size by at least min deduction, without rounding
    min_kbytes = int(usable_kbytes / (1.0 - mindeduct))
    # increase mem size further by 2**n rounding, by 0..roundKb or more
    round_kbytes = int(usable_kbytes / (1.0 - maxdeduct)) - min_kbytes
    # find least binary roundup 2**n that covers worst-cast roundKb
    mod2n = 1 << int(math.ceil(math.log(round_kbytes, 2)))
    # have round_kbytes <= mod2n < round_kbytes*2
    # round min_kbytes up to next multiple of mod2n
    phys_kbytes = min_kbytes + mod2n - 1
    phys_kbytes -= phys_kbytes % mod2n  # clear low bits
    self.phys_kbytes = phys_kbytes

  def _GetMemoryInfo(self):
    #TODO yunlian: when the machine in rebooting, it will not return
    #meminfo, the assert does not catch it either
    command = "cat /proc/meminfo"
    ret, self.meminfo, _ = self.ce.CrosRunCommand(command, return_output=True,
                                              machine=self.name,
                                              username="root",
                                              chromeos_root=self.chromeos_root)
    assert ret == 0, "Could not get meminfo from machine: %s" % self.name
    if ret == 0:
      self._ParseMemoryInfo()

  #cpuinfo format is different across architecture
  #need to find a better way to parse it.
  def _ParseCPUInfo(self, cpuinfo):
    return 0

  def _GetCPUInfo(self):
    command = "cat /proc/cpuinfo"
    ret, self.cpuinfo, _ = self.ce.CrosRunCommand(command, return_output=True,
                                              machine=self.name,
                                              username="root",
                                              chromeos_root=self.chromeos_root)
    assert ret == 0, "Could not get cpuinfo from machine: %s" % self.name
    if ret == 0:
      self._ParseCPUInfo(self.cpuinfo)

  def _ComputeMachineChecksumString(self):
    self.checksum_string = ""
    exclude_lines_list = ["MHz", "BogoMIPS", "bogomips"]
    for line in self.cpuinfo.splitlines():
      if not any([e in line for e in exclude_lines_list]):
        self.checksum_string += line
    self.checksum_string += " " + str(self.phys_kbytes)

  def _GetMD5Checksum(self, ss):
    if ss:
      return hashlib.md5(ss).hexdigest()
    else:
      return ""

  def _GetMachineID(self):
    command = "dump_vpd_log --full --stdout"
    _, if_out, _ = self.ce.CrosRunCommand(command, return_output=True,
                                            machine=self.name,
                                            chromeos_root=self.chromeos_root)
    b = if_out.splitlines()
    a = [l for l in b if "Product" in l]
    if len(a):
      self.machine_id = a[0]
      return
    command = "ifconfig"
    ret, if_out, _ = self.ce.CrosRunCommand(command, return_output=True,
                                            machine=self.name,
                                            chromeos_root=self.chromeos_root)
    b = if_out.splitlines()
    a = [l for l in b if "HWaddr" in l]
    if len(a):
      self.machine_id = "_".join(a)
      return
    a = [l for l in b if "ether" in l]
    if len(a):
      self.machine_id = "_".join(a)
      return
    assert 0, "Could not get machine_id from machine: %s" % self.name

  def __str__(self):
    l = []
    l.append(self.name)
    l.append(str(self.image))
    l.append(str(self.checksum))
    l.append(str(self.locked))
    l.append(str(self.released_time))
    return ", ".join(l)


class MachineManager(object):
  """Lock, image and unlock machines locally for benchmark runs.

  This class contains methods and calls to lock, unlock and image
  machines and distribute machines to each benchmark run.  The assumption is
  that all of the machines for the experiment have been globally locked
  (using an AFE server) in the ExperimentRunner, but the machines still need
  to be locally locked/unlocked (allocated to benchmark runs) to prevent
  multiple benchmark runs within the same experiment from trying to use the
  same machine at the same time.
  """
  def __init__(self, chromeos_root, acquire_timeout, log_level, locks_dir,
               cmd_exec=None, lgr=None):
    self._lock = threading.RLock()
    self._all_machines = []
    self._machines = []
    self.image_lock = threading.Lock()
    self.num_reimages = 0
    self.chromeos_root = None
    self.machine_checksum = {}
    self.machine_checksum_string = {}
    self.acquire_timeout = acquire_timeout
    self.log_level = log_level
    self.locks_dir = None
    self.ce = cmd_exec or command_executer.GetCommandExecuter(
        log_level=self.log_level)
    self.logger = lgr or logger.GetLogger()

    self._initialized_machines = []
    self.chromeos_root = chromeos_root

  def ImageMachine(self, machine, label):
    if label.image_type == "local":
      checksum = ImageChecksummer().Checksum(label, self.log_level)
    elif label.image_type == "trybot":
      checksum = machine._GetMD5Checksum(label.chromeos_image)
    else:
      checksum = None

    if checksum and (machine.checksum == checksum):
      return
    chromeos_root = label.chromeos_root
    if not chromeos_root:
      chromeos_root = self.chromeos_root
    image_chromeos_args = [image_chromeos.__file__,
                           "--no_lock",
                           "--chromeos_root=%s" % chromeos_root,
                           "--image=%s" % label.chromeos_image,
                           "--image_args=%s" % label.image_args,
                           "--remote=%s" % machine.name,
                           "--logging_level=%s" % self.log_level]
    if label.board:
      image_chromeos_args.append("--board=%s" % label.board)

    # Currently can't image two machines at once.
    # So have to serialized on this lock.
    save_ce_log_level = self.ce.log_level
    if self.log_level != "verbose":
      self.ce.log_level = "average"

    with self.image_lock:
      if self.log_level != "verbose":
        self.logger.LogOutput("Pushing image onto machine.")
        self.logger.LogOutput("CMD : python %s "
                                 % " ".join(image_chromeos_args))
      retval = self.ce.RunCommand(" ".join(["python"] + image_chromeos_args))
      if retval:
        cmd = "reboot && exit"
        if self.log_level != "verbose":
          self.logger.LogOutput("reboot & exit.")
        self.ce.CrosRunCommand(cmd, machine=machine.name,
                               chromeos_root=self.chromeos_root)
        time.sleep(60)
        if self.log_level != "verbose":
          self.logger.LogOutput("Pushing image onto machine.")
          self.logger.LogOutput("CMD : python %s "
                                     % " ".join(image_chromeos_args))
        retval = self.ce.RunCommand(" ".join(["python"] + image_chromeos_args))
      if retval:
        raise Exception("Could not image machine: '%s'." % machine.name)
      else:
        self.num_reimages += 1
      machine.checksum = checksum
      machine.image = label.chromeos_image

    self.ce.log_level = save_ce_log_level
    return retval

  def ComputeCommonCheckSum(self, label):
    for machine in self.GetMachines(label):
      if machine.machine_checksum:
        self.machine_checksum[label.name] = machine.machine_checksum
        break

  def ComputeCommonCheckSumString(self, label):
    for machine in self.GetMachines(label):
      if machine.checksum_string:
        self.machine_checksum_string[label.name] = machine.checksum_string
        break

  def _TryToLockMachine(self, cros_machine):
    with self._lock:
      assert cros_machine, "Machine can't be None"
      for m in self._machines:
        if m.name == cros_machine.name:
          return

      self._machines.append(cros_machine)
      command = "cat %s" % CHECKSUM_FILE
      ret, out, _ = self.ce.CrosRunCommand(
          command, return_output=True, chromeos_root=self.chromeos_root,
          machine=cros_machine.name)
      if ret == 0:
        cros_machine.checksum = out.strip()

  # This is called from single threaded mode.
  def AddMachine(self, machine_name):
    with self._lock:
      for m in self._all_machines:
        assert m.name != machine_name, "Tried to double-add %s" % machine_name
        if self.log_level != "verbose":
          self.logger.LogOutput("Setting up remote access to %s"
                              % machine_name)
          self.logger.LogOutput("Checking machine characteristics for %s"
                              % machine_name)
      cm = CrosMachine(machine_name, self.chromeos_root, self.log_level)
      if cm.machine_checksum:
        self._all_machines.append(cm)


  def AreAllMachineSame(self, label):
    checksums = [m.machine_checksum for m in self.GetMachines(label)]
    return len(set(checksums)) == 1


  def RemoveMachine(self, machine_name):
    with self._lock:
      self._machines = [m for m in self._machines
                        if m.name != machine_name]

  def ForceSameImageToAllMachines(self, label):
    machines = self.GetMachines(label)
    for m in machines:
      self.ImageMachine(m, label)
      m.SetUpChecksumInfo()

  def AcquireMachine(self, chromeos_image, label, throw=False):
    if label.image_type == "local":
      image_checksum = ImageChecksummer().Checksum(label, self.log_level)
    elif label.image_type == "trybot":
      image_checksum = hashlib.md5(chromeos_image).hexdigest()
    else:
      image_checksum = None
    machines = self.GetMachines(label)
    check_interval_time = 120
    with self._lock:
      # Lazily external lock machines
      while self.acquire_timeout >= 0:
        for m in machines:
          new_machine = m not in self._all_machines
          self._TryToLockMachine(m)
          if new_machine:
            m.released_time = time.time()
        if not self.AreAllMachineSame(label):
          if not throw:
            # Log fatal message, which calls sys.exit.  Default behavior.
            self.logger.LogFatal("-- not all the machines are identical")
          else:
            # Raise an exception, which can be caught and handled by calling
            # function.
            raise NonMatchingMachines("Not all the machines are identical")
        if self.GetAvailableMachines(label):
          break
        else:
          sleep_time = max(1, min(self.acquire_timeout, check_interval_time))
          time.sleep(sleep_time)
          self.acquire_timeout -= sleep_time

      if self.acquire_timeout < 0:
        machine_names = []
        for machine in machines:
          machine_names.append(machine.name)
        self.logger.LogFatal("Could not acquire any of the "
                             "following machines: '%s'"
                             % ", ".join(machine_names))

###      for m in self._machines:
###        if (m.locked and time.time() - m.released_time < 10 and
###            m.checksum == image_checksum):
###          return None
      for m in [machine for machine in self.GetAvailableMachines(label)
                if not machine.locked]:
        if image_checksum and (m.checksum == image_checksum):
          m.locked = True
          m.test_run = threading.current_thread()
          return m
      for m in [machine for machine in self.GetAvailableMachines(label)
                if not machine.locked]:
        if not m.checksum:
          m.locked = True
          m.test_run = threading.current_thread()
          return m
      # This logic ensures that threads waiting on a machine will get a machine
      # with a checksum equal to their image over other threads. This saves time
      # when crosperf initially assigns the machines to threads by minimizing
      # the number of re-images.
      # TODO(asharif): If we centralize the thread-scheduler, we wont need this
      # code and can implement minimal reimaging code more cleanly.
      for m in [machine for machine in self.GetAvailableMachines(label)
                if not machine.locked]:
        if time.time() - m.released_time > 15:
          # The release time gap is too large, so it is probably in the start
          # stage, we need to reset the released_time.
          m.released_time = time.time()
        elif time.time() - m.released_time > 8:
          m.locked = True
          m.test_run = threading.current_thread()
          return m
    return None

  def GetAvailableMachines(self, label=None):
    if not label:
      return self._machines
    return [m for m in self._machines if m.name in label.remote]

  def GetMachines(self, label=None):
    if not label:
      return self._all_machines
    return [m for m in self._all_machines if m.name in label.remote]

  def ReleaseMachine(self, machine):
    with self._lock:
      for m in self._machines:
        if machine.name == m.name:
          assert m.locked == True, "Tried to double-release %s" % m.name
          m.released_time = time.time()
          m.locked = False
          m.status = "Available"
          break

  def __str__(self):
    with self._lock:
      l = ["MachineManager Status:"]
      for m in self._machines:
        l.append(str(m))
      return "\n".join(l)

  def AsString(self):
    with self._lock:
      stringify_fmt = "%-30s %-10s %-4s %-25s %-32s"
      header = stringify_fmt % ("Machine", "Thread", "Lock", "Status",
                                "Checksum")
      table = [header]
      for m in self._machines:
        if m.test_run:
          test_name = m.test_run.name
          test_status = m.test_run.timeline.GetLastEvent()
        else:
          test_name = ""
          test_status = ""

        try:
          machine_string = stringify_fmt % (m.name,
                                            test_name,
                                            m.locked,
                                            test_status,
                                            m.checksum)
        except Exception:
          machine_string = ""
        table.append(machine_string)
      return "Machine Status:\n%s" % "\n".join(table)

  def GetAllCPUInfo(self, labels):
    """Get cpuinfo for labels, merge them if their cpuinfo are the same."""
    dic = {}
    for label in labels:
      for machine in self._all_machines:
        if machine.name in label.remote:
          if machine.cpuinfo not in dic:
            dic[machine.cpuinfo] = [label.name]
          else:
            dic[machine.cpuinfo].append(label.name)
          break
    output = ""
    for key, v in dic.items():
      output += " ".join(v)
      output += "\n-------------------\n"
      output += key
      output += "\n\n\n"
    return output


class MockCrosMachine(CrosMachine):
  def __init__(self, name, chromeos_root, log_level):
    self.name = name
    self.image = None
    self.checksum = None
    self.locked = False
    self.released_time = time.time()
    self.test_run = None
    self.chromeos_root = chromeos_root
    self.checksum_string = re.sub("\d", "", name)
    #In test, we assume "lumpy1", "lumpy2" are the same machine.
    self.machine_checksum =  self._GetMD5Checksum(self.checksum_string)
    self.log_level = log_level

  def IsReachable(self):
    return True


class MockMachineManager(MachineManager):

  def __init__(self, chromeos_root, acquire_timeout, log_level, locks_dir):
    super(MockMachineManager, self).__init__(chromeos_root, acquire_timeout,
                                             log_level,
                                             locks_dir)

  def _TryToLockMachine(self, cros_machine):
    self._machines.append(cros_machine)
    cros_machine.checksum = ""

  def AddMachine(self, machine_name):
    with self._lock:
      for m in self._all_machines:
        assert m.name != machine_name, "Tried to double-add %s" % machine_name
      cm = MockCrosMachine(machine_name, self.chromeos_root, self.log_level)
      assert cm.machine_checksum, ("Could not find checksum for machine %s" %
                                   machine_name)
      self._all_machines.append(cm)

  def AcquireMachine(self, chromeos_image, label, throw=False):
    for machine in self._all_machines:
      if not machine.locked:
        machine.locked = True
        return machine
    return None

  def ImageMachine(self, machine_name, label):
    return 0

  def ReleaseMachine(self, machine):
    machine.locked = False

  def GetMachines(self, label):
    return self._all_machines

  def GetAvailableMachines(self, label):
    return self._all_machines
