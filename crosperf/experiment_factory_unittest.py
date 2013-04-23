#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import unittest

from utils.file_utils import FileUtils

from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
import test_flag

EXPERIMENT_FILE_1 = """
  board: x86-alex
  remote: chromeos-alex3

  benchmark: PageCycler {
    iterations: 3
  }

  image1 {
    chromeos_image: /usr/local/google/cros_image1.bin
  }

  image2 {
    chromeos_image: /usr/local/google/cros_image2.bin
  }
  """


class ExperimentFactoryTest(unittest.TestCase):
  def testLoadExperimentFile1(self):
    experiment_file = ExperimentFile(StringIO.StringIO(EXPERIMENT_FILE_1))
    experiment = ExperimentFactory().GetExperiment(experiment_file, 
                                                   working_directory="",
                                                   log_dir="")
    self.assertEqual(experiment.remote, ["chromeos-alex3"])

    self.assertEqual(len(experiment.benchmarks), 1)
    self.assertEqual(experiment.benchmarks[0].name, "PageCycler")
    self.assertEqual(experiment.benchmarks[0].test_name, "PageCycler")
    self.assertEqual(experiment.benchmarks[0].iterations, 3)

    self.assertEqual(len(experiment.labels), 2)
    self.assertEqual(experiment.labels[0].chromeos_image,
                     "/usr/local/google/cros_image1.bin")
    self.assertEqual(experiment.labels[0].board,
                     "x86-alex")


if __name__ == "__main__":
  FileUtils.Configure(True)
  test_flag.SetTestMode(True)
  unittest.main()
