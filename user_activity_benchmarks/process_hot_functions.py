#!/usr/bin/python2

# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Processes the functions from the pprof(go/pprof) files and CWP(go/cwp) data.

The pprof output files should have the format given by the output of the
pprof --top command. A line containing a statistic should include the flat,
flat%, sum%, cum, cum%, function name and file name, separated by a space.

The CWP hot functions should be specified in a CSV file that should contain the
fields for the function name, the file and the object where that function is
declared and the inclusive count value.

For each pprof output file, the tool will output a file that contains the hot
functions present also in the CWP hot functions file. Afterwards, it extracts
the functions that are present in the CWP functions file and not in the
pprof output files.

Optionally, it will organize the extra CWP functions in groups that have to
represent a ChromeOS component. A function belongs to a group that is defined
by a given file path if it is declared in a file that shares that path.
"""

import argparse
import csv
import os
import re
import sys


class HotFunctionsProcessor(object):
  """Does the pprof and CWP output processing.

  Extracts the common and extra functions from the pprof output files, based on
  the provided CWP functions.
  """

  # Constants used to identify if a function is common in the pprof and CWP
  # files.
  COMMON_FUNCTION = 1
  NOT_COMMON_FUNCTION = 0

  def __init__(self, pprof_path, cwp_functions_file, common_functions_path,
               extra_cwp_functions_file, cwp_function_groups_file,
               cwp_function_groups_statistics_file,
               cwp_function_groups_file_prefix):
    """Initializes the HotFunctionsProcessor.

    Args:
      pprof_path: The directory containing the pprof output files.
      cwp_functions_file: The file containing the CWP data.
      common_functions_path: The directory where the files with the CWP and
        pprof common functions should be stored.
      extra_cwp_functions_file: The file where should be stored the CWP
        functions that are not in the given pprof output files.
      cwp_function_groups_file: The name of the file containing the groups of
        functions.
      cwp_function_groups_statistics_file: The name of the file containing the
        statistics for the function groups.
      cwp_function_groups_file_prefix: The prefix of the files that will store
        the function statistics for each function group.
    """
    self._pprof_path = pprof_path
    self._cwp_functions_file = cwp_functions_file
    self._common_functions_path = common_functions_path
    self._extra_cwp_functions_file = extra_cwp_functions_file
    self._cwp_function_groups_file = cwp_function_groups_file
    self._cwp_function_groups_statistics_file = \
        cwp_function_groups_statistics_file
    self._cwp_function_groups_file_prefix = cwp_function_groups_file_prefix

  def ProcessHotFunctions(self):
    """Does the processing of the hot functions."""
    cwp_statistics = \
      self.ExtractCommonFunctions(self._pprof_path,
                                   self._common_functions_path,
                                   self._cwp_functions_file)

    self.ExtractExtraFunctions(cwp_statistics, self._extra_cwp_functions_file)
    if all([self._cwp_function_groups_file,
            self._cwp_function_groups_statistics_file,
            self._cwp_function_groups_file_prefix]):
      self.GroupExtraFunctions(cwp_statistics,
                               self._cwp_function_groups_file_prefix,
                               self._cwp_function_groups_file,
                               self._cwp_function_groups_statistics_file)

  def ParseCWPStatistics(self, cwp_statistics_file_name):
    """Parses the contents of the file containing the CWP data.

    A line contains the name of the function, the corresponding filenames, the
    object files and their inclusive count values in CSV format.

    Args:
      cwp_statistics_file_name: The name of the file containing the CWP data
      in CSV format.

    Returns:
      A dict containing the CWP statistics. The key contains the name of the
      functions with the file name comma separated. The value represents a
      tuple with the statistics and a marker to identify if the function is
      present in one of the pprof files.
    """
    cwp_statistics = {}

    with open(cwp_statistics_file_name) as cwp_statistics_file:
      statistics_reader = csv.DictReader(cwp_statistics_file, delimiter=',')

      for statistic in statistics_reader:
        function_name = statistic['function']
        file_name = os.path.normpath(statistic['file'])
        dso_name = statistic['dso']
        inclusive_count = statistic['inclusive_count']

        # We ignore the lines that have empty fields(i.e they specify only the
        # addresses of the functions and the inclusive counts values).
        if all([function_name, file_name, dso_name, inclusive_count]):
          key = '%s,%s' % (function_name, file_name)
          value = \
            ('%s,%s' % (dso_name, inclusive_count), self.NOT_COMMON_FUNCTION)
          # All the functions are marked as NOT_COMMON_FUNCTION.
          cwp_statistics[key] = value

    return cwp_statistics

  def ExtractCommonFunctions(self, pprof_path, common_functions_path,
                             cwp_functions_file):
    """Extracts the common functions of the pprof files and the CWP file.

    For each pprof file, it creates a separate file with the same name
    containing the common functions, that will be placed in the
    common_functions_path directory.

    The resulting file is CSV format, containing the following fields:
    function name, file name, object, inclusive count, flat, flat%, sum%, cum,
    cum%.

    It builds a dict of the CWP statistics and if a function is common, it is
    marked as a COMMON_FUNCTION.

    Args:
      pprof_path: The directory with the pprof files.
      common_functions_path: The directory with the common functions files.
      cwp_functions_file: The file with the CWP data.

    Returns:
      A dict containing the CWP statistics with the common functions marked as
      COMMON_FUNCTION.
    """
    # Get the list of pprof files from the given path.
    pprof_files = os.listdir(pprof_path)
    cwp_statistics = self.ParseCWPStatistics(cwp_functions_file)
    function_statistic_regex = re.compile(r'\S+\s+\S+%\s+\S+%\s+\S+\s+\S+%')
    function_regex = re.compile(r'[a-zA-Z0-9-_:.~\[\]]+')
    # TODO(evelinad): Consider the case where the file name can have other
    # characters.
    file_regex = re.compile(r'[a-zA-Z0-9-/_.]+')

    for pprof_file in pprof_files:
      # In the pprof output, the statistics of the functions start from the
      # 8th line.
      with open(os.path.join(pprof_path, pprof_file), 'r') as input_file:
        pprof_statistics = input_file.readlines()[6:]
      output_lines = \
        ['function,file,dso,inclusive_count,flat,flat%,sum%,cum,cum%']

      for pprof_statistic in pprof_statistics:
        function_statistic_match = \
          function_statistic_regex.search(pprof_statistic)
        function_statistic = \
          ','.join(function_statistic_match.group(0).split())
        lookup_index = function_statistic_match.end()
        function_match = function_regex.search(pprof_statistic[lookup_index:])
        function_name = function_match.group(0)
        lookup_index += function_match.end()
        file_match = file_regex.search(pprof_statistic[lookup_index:])
        if file_match:
          key = ",".join([function_name, os.path.normpath(file_match.group(0))])
        else:
          key = function_name

        if key in cwp_statistics:
          cwp_statistic = cwp_statistics[key]
          output_lines.append(','.join([key, cwp_statistic[0],
                                        function_statistic]))
          cwp_statistics[key] = (cwp_statistic[0], self.COMMON_FUNCTION)

      with open(os.path.join(common_functions_path, pprof_file), 'w') \
        as output_file:
        output_file.write('\n'.join(output_lines))

    return cwp_statistics

  @staticmethod
  def ParseFunctionGroups(cwp_function_groups_lines):
    """Parses the contents of the function groups file.

    Args:
      cwp_function_groups_lines: A list of the lines contained in the CWP
        function groups file.
    Returns:
      A list of tuples containing the group name, the file path, the total
      number of inclusive count values for that group, a list that will contain
      the CWP statistics of the functions declared in files that share the file
      path.
    """
    cwp_function_groups = []

    for line in cwp_function_groups_lines:
      group_name, file_path = line.split()
      cwp_function_groups.append((group_name, file_path, 0, []))

    return cwp_function_groups

  def GroupExtraFunctions(self, cwp_statistics, cwp_function_groups_file_prefix,
                          cwp_function_groups_file,
                          cwp_function_groups_statistics_file):
    """Groups the functions that are in the CWP statistics and not in the pprof
    output. A function belongs to a group that is defined by a given file path
    if it is declared in a file that shares that path.

    Writes the data of the functions that belong to a group in a file, sorted
    by their inclusive count value, in descendant order. The file name is
    composed by the cwp_function_groups_file_prefix and the name of the group.
    The file is in CSV format, containing the fields: function name, file name,
    object name, inclusive count.

    It creates a CSV file containing the name of the groups, their
    common path, the total inclusive count value of all the functions declared
    in files that share the common path, sorted in descendant order by the
    inclusive count value.

    Args:
      cwp_statistics: A dict containing the CWP statistics.
      cwp_function_groups_file_prefix: The prefix used for naming the files that
        the function data for a specific group.
      cwp_function_groups_file: The name of the file containing the groups of
        functions.
      cwp_function_groups_statistics_file: The name of the file that will
        contain the statistics for the function groups.
    """
    with open(cwp_function_groups_file, 'r') as input_file:
      cwp_function_groups = self.ParseFunctionGroups(input_file.readlines())

    for function, statistics in cwp_statistics.iteritems():
      if statistics[1] == self.COMMON_FUNCTION:
        continue
      file_name = function.split(',')[1]
      group_inclusive_count = int(statistics[0].split(',')[1])
      for i, group in enumerate(cwp_function_groups):
        group_common_path = group[1]

        # The order of the groups mentioned in the cwp_functions_groups
        # matters. A function declared in a file will belong to the first
        # mentioned group that matches it's path to the one of the file.
        # It is possible to have multiple paths that belong to the same group.
        if group_common_path in file_name:
          group_name = group[0]
          group_inclusive_count += group[2]
          group_lines = group[3]

          group_lines.append(','.join([function, statistics[0]]))
          cwp_function_groups[i] = (group_name, group_common_path,
                                    group_inclusive_count, group_lines)
          break

    group_statistics_lines = []

    for group_name, group_path, group_inclusive_count, group_lines in \
        cwp_function_groups:
      group_statistics_lines.append(','.join([group_name, group_path,
                                              str(group_inclusive_count)]))
      if group_lines:
        # Sort the output in descendant order based on the inclusive_count
        # value.
        group_lines.sort(key=lambda x: int(x.split(',')[-1]), reverse=True)
        group_lines.insert(0, 'function,file,dso,inclusive_count')
        group_file_name = cwp_function_groups_file_prefix + group_name

        with open(group_file_name, 'w') as output_file:
          output_file.write('\n'.join(group_lines))

    group_statistics_lines.sort(
        key=lambda x: int(x.split(',')[2]), reverse=True)
    group_statistics_lines.insert(0, 'group,shared_path,inclusive_count')

    with open(cwp_function_groups_statistics_file, 'w') as output_file:
      output_file.write('\n'.join(group_statistics_lines))

  def ExtractExtraFunctions(self, cwp_statistics, extra_cwp_functions_file):
    """Gets the functions that are in the CWP file, but not in the pprof output.

    Writes the functions and their statistics in the extra_cwp_functions_file
    file. The output is sorted based on the inclusive_count value. The file is
    in CSV format, containing the fields: function name, file name, object name,
    inclusive count.

    Args:
      cwp_statistics: A dict containing the CWP statistics.
      extra_cwp_functions_file: The file where should be stored the CWP
        functions and statistics that are marked as NOT_COMMON_FUNCTIONS.
    """
    output_lines = []

    for function, statistics in cwp_statistics.iteritems():
      if statistics[1] == self.NOT_COMMON_FUNCTION:
        output_lines.append(','.join([function, statistics[0]]))

    with open(extra_cwp_functions_file, 'w') as output_file:
      output_lines.sort(key=lambda x: int(x.split(',')[-1]), reverse=True)
      output_lines.insert(0, 'function,file,dso,inclusive_count')
      output_file.write('\n'.join(output_lines))


def ParseArguments(arguments):
  parser = argparse.ArgumentParser()

  parser.add_argument(
      '-p',
      '--pprof_path',
      dest='pprof_path',
      required=True,
      help='The directory containing the pprof output files.')
  parser.add_argument(
      '-w',
      '--cwp_hot_functions_file',
      dest='cwp_hot_functions_file',
      required=True,
      help='The CSV file containing the CWP hot functions. The '
      'file should include the name of the functions, the '
      'file names with the definition, the object file '
      'and the CWP inclusive count values, comma '
      'separated.')
  parser.add_argument(
      '-c',
      '--common_functions_path',
      dest='common_functions_path',
      required=True,
      help='The directory containing the files with the pprof '
      'and CWP common functions. A file will contain all '
      'the hot functions from a pprof output file that '
      'are also included in the CWP hot functions file. '
      'The files with the common functions will have the '
      'same names with the corresponding pprof output '
      'files.')
  parser.add_argument(
      '-e',
      '--extra_cwp_functions_file',
      dest='extra_cwp_functions_file',
      required=True,
      help='The file that will contain the CWP hot functions '
      'that are not in any of the pprof output files. '
      'The file should include the name of the functions, '
      'the file names with the definition, the object '
      'file and the CWP inclusive count values, comma '
      'separated.')
  parser.add_argument(
      '-g',
      '--cwp_function_groups_file',
      dest='cwp_function_groups_file',
      help='The file that will contain the CWP function groups.'
      'A line consists in the group name and a file path. A group must '
      'represent a ChromeOS component.')
  parser.add_argument(
      '-s',
      '--cwp_function_groups_statistics_file',
      dest='cwp_function_groups_statistics_file',
      help='The file that will contain the total inclusive count values of CWP '
      'function groups in CSV format. A line will contain the name of the '
      'group, the common path, the total inclusive count value of all the'
      'functions declared in files that share the common path.')
  parser.add_argument(
      '-x',
      '--cwp_function_groups_file_prefix',
      dest='cwp_function_groups_file_prefix',
      help='The prefix of the files that will store the function statistics '
      'for each function group.')

  options = parser.parse_args(arguments)

  return options


def Main(argv):
  options = ParseArguments(argv)

  hot_functions_processor = HotFunctionsProcessor(options.pprof_path,
    options.cwp_hot_functions_file, options.common_functions_path,
    options.extra_cwp_functions_file, options.cwp_function_groups_file,
    options.cwp_function_groups_statistics_file,
    options.cwp_function_groups_file_prefix)

  hot_functions_processor.ProcessHotFunctions()


if __name__ == '__main__':
  Main(sys.argv[1:])
