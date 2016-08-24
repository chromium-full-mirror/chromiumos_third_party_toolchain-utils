#!/usr/bin/python2

# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for the process_hot_functions module."""

from process_hot_functions import HotFunctionsProcessor, ParseArguments

import mock
import os
import shutil
import tempfile
import unittest


class ParseArgumentsTest(unittest.TestCase):
  """Test class for command line argument parsing."""

  def __init__(self, *args, **kwargs):
    super(ParseArgumentsTest, self).__init__(*args, **kwargs)

  def testParseArguments(self):
    arguments = \
      ['-p', 'dummy_pprof', '-c', 'dummy_common', '-e', 'dummy_extra', '-w',
       'dummy_cwp']
    options = ParseArguments(arguments)

    self.assertEqual(options.pprof_path, 'dummy_pprof')
    self.assertEqual(options.cwp_hot_functions_file, 'dummy_cwp')
    self.assertEqual(options.common_functions_path, 'dummy_common')
    self.assertEqual(options.extra_cwp_functions_file, 'dummy_extra')

  @mock.patch('sys.exit')
  def testDeathParseArguments(self, sys_exit_method):
    self.assertFalse(sys_exit_method.called)
    ParseArguments([])
    self.assertTrue(sys_exit_method.called)
    self.assertNotEqual(sys_exit_method.return_value, 0)


class HotFunctionsProcessorTest(unittest.TestCase):
  """Test class for HotFunctionsProcessor class."""

  def __init__(self, *args, **kwargs):
    super(HotFunctionsProcessorTest, self).__init__(*args, **kwargs)
    self._pprof_path = 'testdata/input/pprof'
    self._cwp_functions_file = 'testdata/input/cwp_functions_file.csv'
    self._cwp_functions_file_parsing = \
      'testdata/input/parse_cwp_statistics.csv'
    self._common_functions_path = ''
    self._expected_common_functions_path = 'testdata/expected/pprof_common'
    self._extra_cwp_functions_file = ''

  def _CreateHotFunctionsProcessor(self, extra_cwp_functions_file):
    return HotFunctionsProcessor(self._pprof_path, self._cwp_functions_file,
                                 self._common_functions_path,
                                 extra_cwp_functions_file)

  @mock.patch.object(HotFunctionsProcessor, 'ExtractCommonFunctions')
  @mock.patch.object(HotFunctionsProcessor, 'ExtractExtraFunctions')
  def testProcessHotFunctions(self, common_functions_method,
                              extra_functions_method):
    hot_functions_processor = self._CreateHotFunctionsProcessor(
        self._extra_cwp_functions_file)

    hot_functions_processor.ProcessHotFunctions()

    self.assertTrue(common_functions_method.called)
    self.assertTrue(extra_functions_method.called)
    self.assertEqual(common_functions_method.call_count, 1)
    self.assertEqual(extra_functions_method.call_count, 1)

  def testParseCWPStatistics(self):
    cwp_statistics = {'dummy_method1,dummy_file1': ('dummy_object1,1', 0),
                      'dummy_method2,dummy_file2': ('dummy_object2,2', 0),
                      'dummy_method3,dummy_file3': ('dummy_object3,3', 0),
                      'dummy_method4,dummy_file4': ('dummy_object4,4', 0)}
    hot_functions_processor = self._CreateHotFunctionsProcessor(
        self._extra_cwp_functions_file)
    result = hot_functions_processor.ParseCWPStatistics(
        self._cwp_functions_file_parsing)

    self.assertDictEqual(result, cwp_statistics)

  def testExtractCommonFunctions(self):
    hot_functions_processor = self._CreateHotFunctionsProcessor(
        self._extra_cwp_functions_file)
    common_functions_path = tempfile.mkdtemp()
    hot_functions_processor.ExtractCommonFunctions(self._pprof_path,
                                                   common_functions_path,
                                                   self._cwp_functions_file)
    expected_files = \
      [os.path.join(self._expected_common_functions_path, expected_file)
       for expected_file in os.listdir(self._expected_common_functions_path)]
    result_files = \
      [os.path.join(common_functions_path, result_file)
       for result_file in os.listdir(common_functions_path)]

    expected_files.sort()
    result_files.sort()

    for expected_file_name, result_file_name in \
      zip(expected_files, result_files):
      with open(expected_file_name) as expected_file, \
        open(result_file_name) as result_file:
        expected_output_lines = expected_file.readlines()
        result_output_lines = result_file.readlines()
        self.assertListEqual(expected_output_lines, result_output_lines)
    shutil.rmtree(common_functions_path)

  def testExtractExtraFunctions(self):
    cwp_statistics = {'dummy_method1,dummy_file1': ('dummy_object1,1', 0),
                      'dummy_method2,dummy_file2': ('dummy_object2,2', 1),
                      'dummy_method3,dummy_file3': ('dummy_object3,3', 1),
                      'dummy_method4,dummy_file4': ('dummy_object4,4', 0)}
    expected_output_lines = ['function,file,dso,inclusive_count\n',
                             'dummy_method1,dummy_file1,dummy_object1,1\n',
                             'dummy_method4,dummy_file4,dummy_object4,4']
    temp_file, temp_filename = tempfile.mkstemp()
    hot_functions_processor = self._CreateHotFunctionsProcessor(temp_filename)
    os.close(temp_file)

    hot_functions_processor.ExtractExtraFunctions(cwp_statistics, temp_filename)

    with open(temp_filename) as result_file:
      result_output_lines = result_file.readlines()

    self.assertListEqual(result_output_lines, expected_output_lines)
    os.remove(temp_filename)


if __name__ == '__main__':
  unittest.main()
