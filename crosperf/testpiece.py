#!/usr/bin/python

from benchmark import Benchmark
from collections import defaultdict

# Find Label for a DUT. This is done by iterating all the labels (usually < 10)
# and compare each lable's image with Dut's image (how?) and also check DUT's
# name against labels' remote (if presented). This could return None if a DUT
# has an image that is not listed in any label.

def FindLabelForDut(dut)
    # ...
    pass


class DUT(object):

    # Device under test.
    #   name_ - the hostname/ip of the machine
    #   label_ - the corresponding label or None.
    #   board_ - board (optional)

    def __init__(self, name, board):
        self.name_ = name
        # Maybe None before any reimaging happens.
        self.label_ = FindLabelForDut(self)

    def ReImage(self, label):
        call_utility_function_to_reimage(self, label)
        self.label_ = label


class TestPiece(object):

    # Minimal units to be scheduled
    #   benchmark - as described in benchmark.py module
    #   nth       - each TestPiece may run many times, this is the idx
    #   label     - TestPiece run against

    def __init__(self, benchmark, nth, label):
        self.benchmark_ = benchmark
        self.nth_ = nth
        self.label_ = label


class TestPiecePool(object):

    # label_tpl_map_ - label to TestPiece list mapping.
    # label_num_map_ - label to num of deployment mapping.

    def __init__(self, test_piece_list):
        self.label_tpl_map_ = defaultdict(lambda: [])
        self.label_num_map_ = defaultdict(lambda: 0)
        for tp in test_piece_list:
            self.label_tpl_map_[tp.label_].append(tp)
            self.label_num_map_[tp.label_] = 0

    # This is usually called by multiple threads.

    def GetTestPiece(self, dut):
        tp = GetTestPieceInternal(self, dut)
        while tp is None:
            # The current dut image does not match any experiment labels,
            # request reimage.
            label = self.FindReImageCandidate(self)
            if lable is None:
                # We don't have any label that this machine can reimage to. On
                # return, the dut thread will finish.
                return None
            dut.ReImage(label)
            tp = GetTestPieceInternal(self, dut)
        return tp

    def _GetTestPieceInternal(self, dut):
        if dut.label_ is not None and dut.label_ in self.label_tpl_map_:
            tp_list = self.label_tpl_map_[dut.label_]
            tp = None
            ##### Lock on tp_list
            if len(tp_list):
                tp = tp_list.pop()
                if not len(tp_list):
                    #### Lock on self.label_tpl_map_
                    del self.label_tpl_map_[dut.label]
                    #### Unlock on self.label_tpl_map_
            ##### Unlock on tp_list
            return tp
        return None

    def _FindReImageCandidate(self, dut):
        # We will pick up the image desc with minimal deployment number.
        minlabel, minnum = None, 999999
        for label, num in self.label_num_map_.iteritems():
            if (num < minnum and len(self.label_tpl_map_[label]) > 0 and
                label.remote is None or dut.name_ in label.remote):
                minlabel = label
                minnum = num
        if minlabel is not None:
            #### Lock on self.label_num_map_
            self.label_num_map_[minlabel] += 1
            #### Unlock on self.label_num_map_

        # minlabel may be None
        return minlabel
