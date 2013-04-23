#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from utils.tabulator import *

from column_chart import ColumnChart
from results_organizer import ResultOrganizer
from perf_table import PerfTable


class ResultsReport(object):
  MAX_COLOR_CODE = 255
  PERF_ROWS = 5

  def __init__(self, experiment):
    self.experiment = experiment
    self.benchmark_runs = experiment.benchmark_runs
    self.labels = experiment.labels
    self.benchmarks = experiment.benchmarks
    self.baseline = self.labels[0]

  def _SortByLabel(self, runs):
    labels = {}
    for benchmark_run in runs:
      if benchmark_run.label_name not in labels:
        labels[benchmark_run.label_name] = []
      labels[benchmark_run.label_name].append(benchmark_run)
    return labels

  def GetFullTables(self, perf=False):
    columns = [Column(NonEmptyCountResult(),
                      Format(),
                      "Completed"),
               Column(RawResult(),
                      Format()),
               Column(MinResult(),
                      Format()),
               Column(MaxResult(),
                      Format()),
               Column(AmeanResult(),
                      Format()),
               Column(StdResult(),
                      Format(), "StdDev"),
               Column(CoeffVarResult(),
                      CoeffVarFormat(), "StdDev/Mean"),
               Column(GmeanRatioResult(),
                      RatioFormat(), "GmeanSpeedup"),
               Column(PValueResult(),
                      PValueFormat(), "p-value")
              ]
    if not perf:
      return self._GetTables(self.labels, self.benchmark_runs, columns)
    return self. _GetPerfTables(self.labels, columns)

  def GetSummaryTables(self, perf=False):
    columns = [Column(NonEmptyCountResult(),
                      Format(),
                      "Completed"),
               Column(AmeanResult(),
                      Format()),
               Column(StdResult(),
                      Format(), "StdDev"),
               Column(CoeffVarResult(),
                      CoeffVarFormat(), "StdDev/Mean"),
               Column(GmeanRatioResult(),
                      RatioFormat(), "GmeanSpeedup"),
               Column(GmeanRatioResult(),
                      ColorBoxFormat(), " "),
               Column(PValueResult(),
                      PValueFormat(), "p-value")
              ]
    if not perf:
      return self._GetTables(self.labels, self.benchmark_runs, columns)
    return self. _GetPerfTables(self.labels, columns)

  def _ParseColumn(self, columns, iteration):
    new_column = []
    for column in columns:
      if column.result.__class__.__name__ != "RawResult":
      #TODO(asharif): tabulator should support full table natively.
        new_column.append(column)
      else:
        for i in range(iteration):
          cc = Column(LiteralResult(i), Format(), str(i+1))
          new_column.append(cc)
    return new_column

  def _AreAllRunsEmpty(self, runs):
    for label in runs:
      for dictionary in label:
        if dictionary:
          return False
    return True

  def _GetTableHeader(self, benchmark):
    benchmark_info = ("Benchmark:  {0};  Iterations: {1}"
                      .format(benchmark.name, benchmark.iterations))
    cell = Cell()
    cell.string_value = benchmark_info
    cell.header = True
    return  [[cell]]

  def _GetTables(self, labels, benchmark_runs, columns):
    tables = []
    ro = ResultOrganizer(benchmark_runs, labels, self.benchmarks)
    result = ro.result
    label_name = ro.labels
    for item in result:
      runs = result[item]
      for benchmark in self.benchmarks:
        if benchmark.name == item:
          break
      ben_table = self._GetTableHeader(benchmark)

      if  self._AreAllRunsEmpty(runs):
        cell = Cell()
        cell.string_value = ("This benchmark contains no result."
                             " Is the benchmark name valid?")
        cell_table = [[cell]]
      else:
        tg = TableGenerator(runs, label_name)
        table = tg.GetTable()
        parsed_columns = self._ParseColumn(columns, benchmark.iterations)
        tf = TableFormatter(table, parsed_columns)
        cell_table = tf.GetCellTable()
      tables.append(ben_table)
      tables.append(cell_table)
    return tables

  def _GetPerfTables(self, labels, columns):
    tables = []
    label_names = [label.name for label in labels]
    p_table = PerfTable(self.experiment, label_names)

    if not p_table.perf_data:
      return tables

    for benchmark in p_table.perf_data:
      ben = None
      for ben in self.benchmarks:
        if ben.name == benchmark:
          break

      ben_table = self._GetTableHeader(ben)
      tables.append(ben_table)
      benchmark_data = p_table.perf_data[benchmark]
      row_info = p_table.row_info[benchmark]
      table = []
      for event in benchmark_data:
        tg = TableGenerator(benchmark_data[event], label_names,
                            sort=TableGenerator.SORT_BY_VALUES_DESC)
        table = tg.GetTable(max(self.PERF_ROWS, row_info[event]))
        parsed_columns = self._ParseColumn(columns, ben.iterations)
        tf = TableFormatter(table, parsed_columns)
        tf.GenerateCellTable()
        tf.AddColumnName()
        tf.AddLabelName()
        tf.AddHeader(str(event))
        table = tf.GetCellTable(headers=False)
        tables.append(table)
    return tables

  def PrintTables(self, tables, out_to):
    output = ""
    if not tables:
      return output
    for table in tables:
      if out_to == "HTML":
        tp = TablePrinter(table, TablePrinter.HTML)
      elif out_to == "PLAIN":
        tp = TablePrinter(table, TablePrinter.PLAIN)
      elif out_to == "CONSOLE":
        tp = TablePrinter(table, TablePrinter.CONSOLE)
      elif out_to == "TSV":
        tp = TablePrinter(table, TablePrinter.TSV)
      elif out_to == "EMAIL":
        tp = TablePrinter(table, TablePrinter.EMAIL)
      else:
        pass
      output += tp.Print()
    return output


class TextResultsReport(ResultsReport):
  TEXT = """
===========================================
Results report for: '%s'
===========================================

-------------------------------------------
Summary
-------------------------------------------
%s


Number re-images: %s

-------------------------------------------
Benchmark Run Status
-------------------------------------------
%s


-------------------------------------------
Perf Data
-------------------------------------------
%s



Experiment File
-------------------------------------------
%s


CPUInfo
-------------------------------------------
%s
===========================================
"""

  def __init__(self, experiment, email=False):
    super(TextResultsReport, self).__init__(experiment)
    self.email = email

  def GetStatusTable(self):
    """Generate the status table by the tabulator."""
    table = [["", ""]]
    columns = [Column(LiteralResult(iteration=0), Format(), "Status"),
               Column(LiteralResult(iteration=1), Format(), "Failing Reason")]

    for benchmark_run in self.benchmark_runs:
      status = [benchmark_run.name, [benchmark_run.timeline.GetLastEvent(),
                                     benchmark_run.failure_reason]]
      table.append(status)
    tf = TableFormatter(table, columns)
    cell_table = tf.GetCellTable()
    return [cell_table]

  def GetReport(self):
    """Generate the report for email and console."""
    status_table = self.GetStatusTable()
    summary_table = self.GetSummaryTables()
    full_table = self.GetFullTables()
    perf_table = self.GetSummaryTables(perf=True)
    if not perf_table:
      perf_table = None
    if not self.email:
      return self.TEXT % (self.experiment.name,
                          self.PrintTables(summary_table, "CONSOLE"),
                          self.experiment.machine_manager.num_reimages,
                          self.PrintTables(status_table, "CONSOLE"),
                          self.PrintTables(perf_table, "CONSOLE"),
                          self.experiment.experiment_file,
                          self.experiment.machine_manager.GetAllCPUInfo(
                              self.experiment.labels))

    return self.TEXT % (self.experiment.name,
                        self.PrintTables(summary_table, "EMAIL"),
                        self.experiment.machine_manager.num_reimages,
                        self.PrintTables(status_table, "EMAIL"),
                        self.PrintTables(perf_table, "EMAIL"),
                        self.experiment.experiment_file,
                        self.experiment.machine_manager.GetAllCPUInfo(
                            self.experiment.labels))


class HTMLResultsReport(ResultsReport):

  HTML = """
<html>
  <head>
    <style type="text/css">

body {
  font-family: "Lucida Sans Unicode", "Lucida Grande", Sans-Serif;
  font-size: 12px;
}

pre {
  margin: 10px;
  color: #039;
  font-size: 14px;
}

.chart {
  display: inline;
}

.hidden {
  visibility: hidden;
}

.results-section {
  border: 1px solid #b9c9fe;
  margin: 10px;
}

.results-section-title {
  background-color: #b9c9fe;
  color: #039;
  padding: 7px;
  font-size: 14px;
  width: 200px;
}

.results-section-content {
  margin: 10px;
  padding: 10px;
  overflow:auto;
}

#box-table-a {
  font-size: 12px;
  width: 480px;
  text-align: left;
  border-collapse: collapse;
}

#box-table-a th {
  padding: 6px;
  background: #b9c9fe;
  border-right: 1px solid #fff;
  border-bottom: 1px solid #fff;
  color: #039;
  text-align: center;
}

#box-table-a td {
  padding: 4px;
  background: #e8edff;
  border-bottom: 1px solid #fff;
  border-right: 1px solid #fff;
  color: #669;
  border-top: 1px solid transparent;
}

#box-table-a tr:hover td {
  background: #d0dafd;
  color: #339;
}

    </style>
    <script type='text/javascript' src='https://www.google.com/jsapi'></script>
    <script type='text/javascript'>
      google.load('visualization', '1', {packages:['corechart']});
      google.setOnLoadCallback(init);
      function init() {
        switchTab('summary', 'html');
        %s
        switchTab('full', 'html');
        drawTable();
      }
      function drawTable() {
        %s
      }
      function switchTab(table, tab) {
        document.getElementById(table + '-html').style.display = 'none';
        document.getElementById(table + '-text').style.display = 'none';
        document.getElementById(table + '-tsv').style.display = 'none';
        document.getElementById(table + '-' + tab).style.display = 'block';
      }
    </script>
  </head>

  <body>
    <div class='results-section'>
      <div class='results-section-title'>Summary Table</div>
      <div class='results-section-content'>
        <div id='summary-html'>%s</div>
        <div id='summary-text'><pre>%s</pre></div>
        <div id='summary-tsv'><pre>%s</pre></div>
      </div>
      %s
    </div>
    %s
    <div class='results-section'>
      <div class='results-section-title'>Charts</div>
      <div class='results-section-content'>%s</div>
    </div>
    <div class='results-section'>
      <div class='results-section-title'>Full Table</div>
      <div class='results-section-content'>
        <div id='full-html'>%s</div>
        <div id='full-text'><pre>%s</pre></div>
        <div id='full-tsv'><pre>%s</pre></div>
      </div>
      %s
    </div>
    <div class='results-section'>
      <div class='results-section-title'>Experiment File</div>
      <div class='results-section-content'>
        <pre>%s</pre>
    </div>
    </div>
  </body>
</html>
"""

  PERF_HTML = """
    <div class='results-section'>
      <div class='results-section-title'>Perf Table</div>
      <div class='results-section-content'>
        <div id='perf-html'>%s</div>
        <div id='perf-text'><pre>%s</pre></div>
        <div id='perf-tsv'><pre>%s</pre></div>
      </div>
      %s
    </div>
"""

  def __init__(self, experiment):
    super(HTMLResultsReport, self).__init__(experiment)

  def _GetTabMenuHTML(self, table):
    return """
<div class='tab-menu'>
  <a href="javascript:switchTab('%s', 'html')">HTML</a>
  <a href="javascript:switchTab('%s', 'text')">Text</a>
  <a href="javascript:switchTab('%s', 'tsv')">TSV</a>
</div>""" % (table, table, table)

  def GetReport(self):
    chart_javascript = ""
    charts = self._GetCharts(self.labels, self.benchmark_runs)
    for chart in charts:
      chart_javascript += chart.GetJavascript()
    chart_divs = ""
    for chart in charts:
      chart_divs += chart.GetDiv()

    summary_table = self.GetSummaryTables()
    full_table = self.GetFullTables()
    perf_table = self.GetSummaryTables(perf=True)
    if perf_table:
      perf_html = self.PERF_HTML % (
          self.PrintTables(perf_table, "HTML"),
          self.PrintTables(perf_table, "PLAIN"),
          self.PrintTables(perf_table, "TSV"),
          self._GetTabMenuHTML("perf")
          )
      perf_init = "switchTab('perf', 'html');"
    else:
      perf_html = ""
      perf_init = ""

    return self.HTML % (perf_init,
                        chart_javascript,
                        self.PrintTables(summary_table, "HTML"),
                        self.PrintTables(summary_table, "PLAIN"),
                        self.PrintTables(summary_table, "TSV"),
                        self._GetTabMenuHTML("summary"),
                        perf_html,
                        chart_divs,
                        self.PrintTables(full_table, "HTML"),
                        self.PrintTables(full_table, "PLAIN"),
                        self.PrintTables(full_table, "TSV"),
                        self._GetTabMenuHTML("full"),
                        self.experiment.experiment_file)

  def _GetCharts(self, labels, benchmark_runs):
    charts = []
    ro = ResultOrganizer(benchmark_runs, labels)
    result = ro.result
    for item in result:
      runs = result[item]
      tg = TableGenerator(runs, ro.labels)
      table = tg.GetTable()
      columns = [Column(AmeanResult(),
                        Format()),
                 Column(MinResult(),
                        Format()),
                 Column(MaxResult(),
                        Format())
                ]
      tf = TableFormatter(table, columns)
      data_table = tf.GetCellTable()

      for i in range(2, len(data_table)):
        cur_row_data = data_table[i]
        test_key = cur_row_data[0].string_value
        title = "{0}: {1}".format(item, test_key.replace("/", ""))
        chart = ColumnChart(title, 300, 200)
        chart.AddColumn("Label", "string")
        chart.AddColumn("Average", "number")
        chart.AddColumn("Min", "number")
        chart.AddColumn("Max", "number")
        chart.AddSeries("Min", "line", "black")
        chart.AddSeries("Max", "line", "black")
        cur_index = 1
        for label in ro.labels:
          chart.AddRow([label, cur_row_data[cur_index].value,
                        cur_row_data[cur_index + 1].value,
                        cur_row_data[cur_index + 2].value])
          if isinstance(cur_row_data[cur_index].value, str):
            chart = None
            break
          cur_index += 3
        if chart:
          charts.append(chart)
    return charts
