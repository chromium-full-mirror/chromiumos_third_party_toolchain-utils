#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The label of benchamrks."""

import os
from utils.file_utils import FileUtils


class Label(object):
  def __init__(self, name, chromeos_image, chromeos_root, board, remote,
               image_args, image_md5sum, cache_dir, chrome_src=None):
    # Expand ~
    chromeos_root = os.path.expanduser(chromeos_root)
    chromeos_image = os.path.expanduser(chromeos_image)

    self.name = name
    self.chromeos_image = chromeos_image
    self.board = board
    self.remote = remote
    self.image_args = image_args
    self.image_md5sum = image_md5sum
    self.cache_dir = cache_dir

    if not chromeos_root:
      chromeos_root = FileUtils().ChromeOSRootFromImage(chromeos_image)
      if not chromeos_root:
        raise Exception("No ChromeOS root given for label '%s' and could not "
                        "determine one from image path: '%s'." %
                        (name, chromeos_image))
    else:
      chromeos_root = FileUtils().CanonicalizeChromeOSRoot(chromeos_root)
      if not chromeos_root:
        raise Exception("Invalid ChromeOS root given for label '%s': '%s'."
                        % (name, chromeos_root))

    self.chromeos_root = chromeos_root
    if not chrome_src:
      self.chrome_src = os.path.join(self.chromeos_root,
          "chroot/var/cache/chromeos-chrome/chrome-src-internal/src")
    else:
      chromeos_root = FileUtils().CanonicalizeChromeOSRoot(chrome_src)


class MockLabel(object):
  def __init__(self, name, chromeos_image, chromeos_root, board, remote,
               image_args, image_md5sum, cache_dir):
    self.name = name
    self.chromeos_image = chromeos_image
    self.board = board
    self.remote = remote
    self.cache_dir = cache_dir
    if not chromeos_root:
      self.chromeos_root = "/tmp/chromeos_root"
    else:
      self.chromeos_root = chromeos_root
    self.image_args = image_args
    self.image_md5sum = image_md5sum
