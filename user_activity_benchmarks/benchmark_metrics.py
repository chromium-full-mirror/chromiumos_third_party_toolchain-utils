# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Computes the metrics for functions, Chrome OS components and benchmarks."""

import collections


def ComputeDistanceForFunction(child_functions_statistics_sample,
                               child_functions_statistics_reference):
  """Computes the distance metric for a function.

  Args:
    child_functions_statistics_sample: A dict that has as a key the name of a
      function and as a value the inclusive count fraction. The keys are
      the child functions of a sample parent function.
    child_functions_statistics_reference: A dict that has as a key the name of
      a function and as a value the inclusive count fraction. The keys are
      the child functions of a reference parent function.
  Returns:
    A float value representing the sum of inclusive count fraction
    differences of pairs of common child functions. If a child function is
    present in a single data set, then we consider the missing inclusive
    count fraction as 0. This value describes the difference in behaviour
    between a sample and the reference parent function.
  """
  # We initialize the distance with a small value to avoid the further
  # division by zero.
  distance = 1.0

  for child_function, inclusive_count_fraction_reference in \
      child_functions_statistics_reference.iteritems():
    inclusive_count_fraction_sample = 0.0

    if child_function in child_functions_statistics_sample:
      inclusive_count_fraction_sample = \
          child_functions_statistics_sample[child_function]
    distance += \
        abs(inclusive_count_fraction_sample -
            inclusive_count_fraction_reference)

  for child_function, inclusive_count_fraction_sample in \
      child_functions_statistics_sample.iteritems():
    if child_function not in child_functions_statistics_reference:
      distance += inclusive_count_fraction_sample

  return distance


def ComputeScoreForFunction(distance, reference_fraction, sample_fraction):
  """Computes the score for a function.

  Args:
    distance: A float value representing the difference in behaviour between
      the sample and the reference function.
    reference_fraction: A float value representing the inclusive count
      fraction of the reference function.
    sample_fraction: A float value representing the inclusive count
      fraction of the sample function.
  Returns:
    A float value representing the score of the function.
  """
  return reference_fraction * sample_fraction / distance


def ComputeMetricsForComponents(cwp_function_groups, function_metrics):
  """Computes the metrics for a set of Chrome OS components.

  For every Chrome OS group, we compute the number of functions matching the
  group, the cumulative and average score, the cumulative and average distance
  of all those functions. A function matches a group if the path of the file
  containing its definition contains the common path describing the group.

  Args:
    cwp_function_groups: A dict having as a key the name of the group and as a
      value a common path describing the group.
    function_metrics: A dict having as a key the name of the function and the
      name of the file where it is declared concatenated by a ',', and as a
      value a tuple containing the distance and the score metrics.
  Returns:
    A dict containing as a key the name of the group and as a value a tuple
    with the group file path, the number of functions matching the group,
    the cumulative and average score, cumulative and average distance of all
    those functions.
  """
  function_groups_metrics = \
      collections.defaultdict(lambda : (0, 0.0, 0.0, 0.0, 0.0))

  for function_key, metric in function_metrics.iteritems():
    function, function_file = function_key.split(',')

    for group, common_path in cwp_function_groups:
      if common_path not in function_file:
        continue

      function_distance = metric[0]
      function_score = metric[1]
      group_statistic = function_groups_metrics[group]

      function_count = group_statistic[1] + 1
      function_distance_cum = function_distance + group_statistic[2]
      function_distance_avg = function_distance_cum / float(function_count)
      function_score_cum = function_score + group_statistic[4]
      function_score_avg = function_score_cum / float(function_count)

      function_groups_metrics[group] = \
          (common_path,
           function_count,
           function_distance_cum,
           function_distance_avg,
           function_score_cum,
           function_score_avg)
      break

  return function_groups_metrics


def ComputeMetricsForBenchmark(function_metrics):
  function_count = len(function_metrics.keys())
  distance_cum = 0.0
  distance_avg = 0.0
  score_cum = 0.0
  score_avg = 0.0

  for distance, score in function_metrics.values():
    distance_cum += distance
    score_cum += score

  distance_avg = distance_cum / float(function_count)
  score_avg = score_cum / float(function_count)
  return function_count, distance_cum, distance_avg, score_cum, score_avg


def ComputeMetricsForBenchmarkSet(benchmark_set_function_metrics,
                                  cwp_function_groups):
  """TODO(evelinad): Add the computation of the metrics for a set of benchmarks.
  """
  raise NotImplementedError()
