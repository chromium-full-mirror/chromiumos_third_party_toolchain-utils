#!/usr/bin/python

# Copyright 2015 The Chromium OS Authors. All rights reserved.

"""Utilities for locking machines."""


import os
import sys
import time

import afe_lock_machine
import file_lock_machine

from utils import logger


def AcquireLock(machines, chromeos_root, timeout=1200):
  """Acquire lock for machine(s) with timeout, using AFE server for locking."""
  start_time = time.time()
  locked = True
  sleep_time = min(10, timeout/10.0)
  while True:
    try:
      afe_lock_machine.AFELockManager(machines, False, chromeos_root,
                                      None).UpdateMachines(True)
      break
    except Exception as e:
      if time.time() - start_time > timeout:
        locked = False
        logger.GetLogger().LogWarning(
          "Could not acquire lock on this machine: {0} within {1} seconds. %s"
          .format(repr(machines), timeout, str(e)))
        break
      time.sleep(sleep_time)
  return locked


def ReleaseLock(machines, chromeos_root):
  """Release locked machine(s), using AFE server for locking."""
  unlocked = True
  try:
    afe_lock_machine.AFELockManager(machines, False, chromeos_root,
                                    None).UpdateMachines(False)
  except Exception as e:
    unlocked = False
    logger.GetLogger().LogWarning("Could not unlock %s. %s" %
                                  (repr(machines), str(e)))
  return unlocked
