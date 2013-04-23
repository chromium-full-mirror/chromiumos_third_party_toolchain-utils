#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import getpass
import glob
import hashlib
import os
import pickle
import re
import tempfile

from utils import command_executer
from utils import misc

from image_checksummer import ImageChecksummer

SCRATCH_BASE = "/home/%s/cros_scratch"
SCRATCH_DIR = SCRATCH_BASE % getpass.getuser()
RESULTS_FILE = "results.txt"
MACHINE_FILE = "machine.txt"
AUTOTEST_TARBALL = "autotest.tbz2"
PERF_RESULTS_FILE = "perf-results.txt"


class Result(object):
  """ This class manages what exactly is stored inside the cache without knowing
  what the key of the cache is. For runs with perf, it stores perf.data,
  perf.report, etc. The key generation is handled by the ResultsCache class.
  """

  def __init__(self, logger, label):
    self._chromeos_root = label.chromeos_root
    self._logger = logger
    self._ce = command_executer.GetCommandExecuter(self._logger)
    self._temp_dir = None
    self.label = label
    self.results_dir = None
    self.perf_data_files = []
    self.perf_report_files = []

  def _CopyFilesTo(self, dest_dir, files_to_copy):
    file_index = 0
    for file_to_copy in files_to_copy:
      if not os.path.isdir(dest_dir):
        command = "mkdir -p %s" % dest_dir
        self._ce.RunCommand(command)
      dest_file = os.path.join(dest_dir,
                               ("%s.%s" % (os.path.basename(file_to_copy),
                                           file_index)))
      ret = self._ce.CopyFiles(file_to_copy,
                               dest_file,
                               recursive=False)
      if ret:
        raise Exception("Could not copy results file: %s" % file_to_copy)

  def CopyResultsTo(self, dest_dir):
    self._CopyFilesTo(dest_dir, self.perf_data_files)
    self._CopyFilesTo(dest_dir, self.perf_report_files)

  def _GetKeyvals(self):
    results_in_chroot = os.path.join(self._chromeos_root,
                                     "chroot", "tmp")
    if not self._temp_dir:
      self._temp_dir = tempfile.mkdtemp(dir=results_in_chroot)
      command = "cp -r {0}/* {1}".format(self.results_dir, self._temp_dir)
      self._ce.RunCommand(command)

    command = ("python generate_test_report --no-color --csv %s" %
               (os.path.join("/tmp", os.path.basename(self._temp_dir))))
    [_, out, _] = self._ce.ChrootRunCommand(self._chromeos_root,
                                            command,
                                            return_output=True)
    keyvals_dict = {}
    tmp_dir_in_chroot = misc.GetInsideChrootPath(self._chromeos_root,
                                                 self._temp_dir)
    for line in out.splitlines():
      tokens = re.split("=|,", line)
      key = tokens[-2]
      if key.startswith(tmp_dir_in_chroot):
        key = key[len(tmp_dir_in_chroot) + 1:]
      value = tokens[-1]
      keyvals_dict[key] = value

    return keyvals_dict

  def _GetResultsDir(self):
    mo = re.search(r"Results placed in (\S+)", self.out)
    if mo:
      result = mo.group(1)
      return result
    raise Exception("Could not find results directory.")

  def _FindFilesInResultsDir(self, find_args):
    if not self.results_dir:
      return None
    command = "find %s %s" % (self.results_dir,
                              find_args)
    ret, out, _ = self._ce.RunCommand(command, return_output=True)
    if ret:
      raise Exception("Could not run find command!")
    return out

  def _GetPerfDataFiles(self):
    return self._FindFilesInResultsDir("-name perf.data").splitlines()

  def _GetPerfReportFiles(self):
    return self._FindFilesInResultsDir("-name perf.data.report").splitlines()

  def _GeneratePerfReportFiles(self):
    perf_report_files = []
    for perf_data_file in self.perf_data_files:
      # Generate a perf.report and store it side-by-side with the perf.data
      # file.
      chroot_perf_data_file = misc.GetInsideChrootPath(self._chromeos_root,
                                                       perf_data_file)
      perf_report_file = "%s.report" % perf_data_file
      if os.path.exists(perf_report_file):
        raise Exception("Perf report file already exists: %s" %
                        perf_report_file)
      chroot_perf_report_file = misc.GetInsideChrootPath(self._chromeos_root,
                                                         perf_report_file)
      command = ("/usr/sbin/perf report "
                 "-n "
                 "--symfs /build/%s "
                 "--vmlinux /build/%s/usr/lib/debug/boot/vmlinux "
                 "--kallsyms /build/%s/boot/System.map-* "
                 "-i %s --stdio "
                 "> %s" %
                 (self._board,
                  self._board,
                  self._board,
                  chroot_perf_data_file,
                  chroot_perf_report_file))
      self._ce.ChrootRunCommand(self._chromeos_root,
                                command)

      # Add a keyval to the dictionary for the events captured.
      perf_report_files.append(
          misc.GetOutsideChrootPath(self._chromeos_root,
                                    chroot_perf_report_file))
    return perf_report_files

  def _GatherPerfResults(self):
    report_id = 0
    for perf_report_file in self.perf_report_files:
      with open(perf_report_file, "r") as f:
        report_contents = f.read()
        for group in re.findall(r"Events: (\S+) (\S+)", report_contents):
          num_events = group[0]
          event_name = group[1]
          key = "perf_%s_%s" % (report_id, event_name)
          value = str(misc.UnitToNumber(num_events))
          self.keyvals[key] = value

  def _PopulateFromRun(self, out, err, retval):
    self._board = self.label.board
    self.out = out
    self.err = err
    self.retval = retval
    self.chroot_results_dir = self._GetResultsDir()
    self.results_dir = misc.GetOutsideChrootPath(self._chromeos_root,
                                                 self.chroot_results_dir)
    self.perf_data_files = self._GetPerfDataFiles()
    # Include all perf.report data in table.
    self.perf_report_files = self._GeneratePerfReportFiles()
    # TODO(asharif): Do something similar with perf stat.

    # Grab keyvals from the directory.
    self._ProcessResults()

  def _ProcessResults(self):
    # Note that this function doesn't know anything about whether there is a
    # cache hit or miss. It should process results agnostic of the cache hit
    # state.
    self.keyvals = self._GetKeyvals()
    self.keyvals["retval"] = self.retval
    # Generate report from all perf.data files.
    # Now parse all perf report files and include them in keyvals.
    self._GatherPerfResults()

  def _PopulateFromCacheDir(self, cache_dir):
    # Read in everything from the cache directory.
    with open(os.path.join(cache_dir, RESULTS_FILE), "r") as f:
      self.out = pickle.load(f)
      self.err = pickle.load(f)
      self.retval = pickle.load(f)

    # Untar the tarball to a temporary directory
    self._temp_dir = tempfile.mkdtemp(dir=os.path.join(self._chromeos_root,
                                                       "chroot", "tmp"))

    command = ("cd %s && tar xf %s" %
               (self._temp_dir,
                os.path.join(cache_dir, AUTOTEST_TARBALL)))
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Could not untar cached tarball")
    self.results_dir = self._temp_dir
    self.perf_data_files = self._GetPerfDataFiles()
    self.perf_report_files = self._GetPerfReportFiles()
    self._ProcessResults()

  def CleanUp(self, rm_chroot_tmp):
    if rm_chroot_tmp and self.results_dir:
      command = "rm -rf %s" % self.results_dir
      self._ce.RunCommand(command)
    if self._temp_dir:
      command = "rm -rf %s" % self._temp_dir
      self._ce.RunCommand(command)

  def StoreToCacheDir(self, cache_dir, machine_manager):
    # Create the dir if it doesn't exist.
    temp_dir = tempfile.mkdtemp()

    # Store to the temp directory.
    with open(os.path.join(temp_dir, RESULTS_FILE), "w") as f:
      pickle.dump(self.out, f)
      pickle.dump(self.err, f)
      pickle.dump(self.retval, f)

    if self.results_dir:
      tarball = os.path.join(temp_dir, AUTOTEST_TARBALL)
      command = ("cd %s && "
                 "tar "
                 "--exclude=var/spool "
                 "--exclude=var/log "
                 "-cjf %s ." % (self.results_dir, tarball))
      ret = self._ce.RunCommand(command)
      if ret:
        raise Exception("Couldn't store autotest output directory.")
    # Store machine info.
    # TODO(asharif): Make machine_manager a singleton, and don't pass it into
    # this function.
    with open(os.path.join(temp_dir, MACHINE_FILE), "w") as f:
      f.write(machine_manager.machine_checksum_string[self.label.name])

    if os.path.exists(cache_dir):
      command = "rm -rf {0}".format(cache_dir)
      self._ce.RunCommand(command)

    command = "mkdir -p {0} && ".format(os.path.dirname(cache_dir))
    command += "chmod g+x {0} && ".format(temp_dir)
    command += "mv {0} {1}".format(temp_dir, cache_dir)
    ret = self._ce.RunCommand(command)
    if ret:
      command = "rm -rf {0}".format(temp_dir)
      self._ce.RunCommand(command)
      raise Exception("Could not move dir %s to dir %s" %
                      (temp_dir, cache_dir))

  @classmethod
  def CreateFromRun(cls, logger, label, out, err, retval, suite="pyauto"):
    if suite == "telemetry":
      result = TelemetryResult(logger, label)
    else:
      result = cls(logger, label)
    result._PopulateFromRun(out, err, retval)
    return result

  @classmethod
  def CreateFromCacheHit(cls, logger, label, cache_dir,
                         suite="pyauto"):
    if suite == "telemetry":
      result = TelemetryResult(logger, label)
    else:
      result = cls(logger, label)
    try:
      result._PopulateFromCacheDir(cache_dir)

    except Exception as e:
      logger.LogError("Exception while using cache: %s" % e)
      return None
    return result

class TelemetryResult(Result):

  def __init__(self, logger, label):
    super(TelemetryResult, self).__init__(logger, label)

  def _PopulateFromRun(self, out, err, retval):
    self.out = out
    self.err = err
    self.retval = retval

    self._ProcessResults()

  def _ProcessResults(self):
    # The output is:
    # url,average_commit_time (ms),...
    # www.google.com,33.4,21.2,...
    # We need to convert to this format:
    # {"www.google.com:average_commit_time (ms)": "33.4",
    #  "www.google.com:...": "21.2"}

    lines = self.out.splitlines()
    self.keyvals = {}

    if not lines:
      return
    labels = lines[0].split(",")
    for line in lines[1:]:
      fields = line.split(",")
      if (len(fields) != len(labels)):
        continue
      for i in range(1, len(labels)):
        key = "%s %s" % (fields[0], labels[i])
        value = fields[i]
        self.keyvals[key] = value
    self.keyvals["retval"] = self.retval

  def _PopulateFromCacheDir(self, cache_dir):
    with open(os.path.join(cache_dir, RESULTS_FILE), "r") as f:
      self.out = pickle.load(f)
      self.err = pickle.load(f)
      self.retval = pickle.load(f)
    self._ProcessResults()


class CacheConditions(object):
  # Cache hit only if the result file exists.
  CACHE_FILE_EXISTS = 0

  # Cache hit if the checksum of cpuinfo and totalmem of
  # the cached result and the new run match.
  MACHINES_MATCH = 1

  # Cache hit if the image checksum of the cached result and the new run match.
  CHECKSUMS_MATCH = 2

  # Cache hit only if the cached result was successful
  RUN_SUCCEEDED = 3

  # Never a cache hit.
  FALSE = 4

  # Cache hit if the image path matches the cached image path.
  IMAGE_PATH_MATCH = 5

  # Cache hit if the uuid of hard disk mataches the cached one

  SAME_MACHINE_MATCH = 6


class ResultsCache(object):
  """ This class manages the key of the cached runs without worrying about what
  is exactly stored (value). The value generation is handled by the Results
  class.
  """
  CACHE_VERSION = 6

  def Init(self, chromeos_image, chromeos_root, test_name, iteration,
           test_args, machine_manager, board, cache_conditions,
           logger_to_use, label, share_users, suite):
    self.chromeos_image = chromeos_image
    self.chromeos_root = chromeos_root
    self.test_name = test_name
    self.iteration = iteration
    self.test_args = test_args,
    self.board = board
    self.cache_conditions = cache_conditions
    self.machine_manager = machine_manager
    self._logger = logger_to_use
    self._ce = command_executer.GetCommandExecuter(self._logger)
    self.label = label
    self.share_users = share_users
    self.suite = suite

  def _GetCacheDirForRead(self):
    matching_dirs = []
    for glob_path in self._FormCacheDir(self._GetCacheKeyList(True)):
      matching_dirs += glob.glob(glob_path)

    if matching_dirs:
      # Cache file found.
      return matching_dirs[0]
    else:
      return None

  def _GetCacheDirForWrite(self):
    return self._FormCacheDir(self._GetCacheKeyList(False))[0]

  def _FormCacheDir(self, list_of_strings):
    cache_key = " ".join(list_of_strings)
    cache_dir = misc.GetFilenameFromString(cache_key)
    if self.label.cache_dir:
      cache_home = os.path.abspath(os.path.expanduser(self.label.cache_dir))
      cache_path = [os.path.join(cache_home, cache_dir)]
    else:
      cache_path = [os.path.join(SCRATCH_DIR, cache_dir)]

    for i in [x.strip() for x in self.share_users.split(",")]:
      path = SCRATCH_BASE % i
      cache_path.append(os.path.join(path, cache_dir))

    return cache_path

  def _GetCacheKeyList(self, read):
    if read and CacheConditions.MACHINES_MATCH not in self.cache_conditions:
      machine_checksum = "*"
    else:
      machine_checksum = self.machine_manager.machine_checksum[self.label.name]
    if read and CacheConditions.CHECKSUMS_MATCH not in self.cache_conditions:
      checksum = "*"
    else:
      checksum = ImageChecksummer().Checksum(self.label)

    if read and CacheConditions.IMAGE_PATH_MATCH not in self.cache_conditions:
      image_path_checksum = "*"
    else:
      image_path_checksum = hashlib.md5(self.chromeos_image).hexdigest()

    if read and CacheConditions.SAME_MACHINE_MATCH not in self.cache_conditions:
      machine_id_checksum = "*"
    else:
      for machine in self.machine_manager.GetMachines(self.label):
        if machine.name == self.label.remote[0]:
          machine_id_checksum = machine.machine_id_checksum
          break

    test_args_checksum = hashlib.md5(
        "".join(self.test_args)).hexdigest()
    return (image_path_checksum,
            self.test_name, str(self.iteration),
            test_args_checksum,
            checksum,
            machine_checksum,
            machine_id_checksum,
            str(self.CACHE_VERSION))

  def ReadResult(self):
    if CacheConditions.FALSE in self.cache_conditions:
      return None
    cache_dir = self._GetCacheDirForRead()

    if not cache_dir:
      return None

    if not os.path.isdir(cache_dir):
      return None

    self._logger.LogOutput("Trying to read from cache dir: %s" % cache_dir)
    result = Result.CreateFromCacheHit(self._logger,
                                       self.label,
                                       cache_dir,
                                       self.suite)
    if not result:
      return None

    if (result.retval == 0 or
        CacheConditions.RUN_SUCCEEDED not in self.cache_conditions):
      return result

    return None

  def StoreResult(self, result):
    cache_dir = self._GetCacheDirForWrite()
    result.StoreToCacheDir(cache_dir, self.machine_manager)


class MockResultsCache(ResultsCache):
  def Init(self, *args):
    pass

  def ReadResult(self):
    return None

  def StoreResult(self, result):
    pass


class MockResult(Result):
  def _PopulateFromRun(self, out, err, retval):
    self.out = out
    self.err = err
    self.retval = retval

