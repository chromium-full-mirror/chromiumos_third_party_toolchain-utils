#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.
"""Utility to display text size for binary file.

A typical usage of this program -
  bin_text_size.py binary_file_name

Below is a sample output -
bin_text_size.py ../hdd2/gcc-4_8-release/3-new/chroot/var/cache/chromeos-chrome/chrome-src-internal/src/out_daisy/Release/obj.target/base_prefs_test_support/base/prefs/testing_pref_service.o
Text size for ../hdd2/gcc-4_8-release/3-new/chroot/var/cache/chromeos-chrome/chrome-src-internal/src/out_daisy/Release/obj.target/base_prefs_test_support/base/prefs/testing_pref_service.o
  .text: 0
  TestingPrefServiceBase::HandleReadError: 4
  base::internal::Invoker::Run: 16
  base::internal::BindStateBase::~BindStateBase: 32
  base::internal::BindStateBase::~BindStateBase: 36
  base::internal::BindState::~BindState: 32
  base::internal::BindState::~BindState: 36
  TestingPrefServiceBase::~TestingPrefServiceBase: 108
  TestingPrefServiceBase::~TestingPrefServiceBase: 24
  TestingPrefServiceSimple::~TestingPrefServiceSimple: 28
  TestingPrefServiceSimple::~TestingPrefServiceSimple: 36
  TestingPrefServiceBase::TestingPrefServiceBase: 324
  TestingPrefServiceSimple::TestingPrefServiceSimple: 132
  TestingPrefServiceSimple::registry: 4
  startup._GLOBAL__sub_I_testing_pref_service.cc: 52
Total text size: 864
"""

import re
import sys

from utils import command_executer
from utils import readelf


def StripPair(s, deli='<>'):
  """Remove everything between "deli".

  For example, for s="func<t=abc,v=template<>,s=default>(a, b)", deli="<>", this
  function returns func(a, b).

  Args:
    s: string to be stripped
    deli: delimeiters to specify the region to be stripped.
  Returns:
    stripped string
  """
  r = []
  lvl = 0
  for c in s:
    if c == deli[0]:
      lvl += 1
      continue
    if c == deli[1]:
      lvl -= 1
      continue
    if lvl == 0:
      r.append(c)
  return ''.join(r)


def DemangleName(name, omit_template_arguments=True):
  """Demangle c++ names to human readable ones.

  This function calls c++filt to do the work.
  Args:
    name: the name to be demangled.
    omit_template_arguments: strip template arguments inside '<>', which makes
    the name much shorter.
  Returns:
    Human readable function names if c++filt succeeds. Otherwise return
    the name unchanged.
  """
  cexec = command_executer.GetCommandExecuter()
  cmd = 'c++filt -p "{0}"'.format(name)
  (ec, output, _) = cexec.RunCommand(
      cmd, return_output=True, print_to_console=False)
  if ec != 0:
    # If error running c++filt, just return as is.
    return name
  result = output.strip()
  if omit_template_arguments:
    result = StripPair(result)
  return result


def Main(args):
  elf = readelf.ReadElf(args[1])
  if not elf:
    print 'Failed to readelf: {0}'.format(args[1])
    return 1

  # Read executable sections.
  text_sections = elf.ReadSections(True)
  if not text_sections:
    print 'Failed to read section info: readelf {0}'.format(args[1])
    return 1

  print 'Text size for {0}'.format(elf.filename)
  size_sum = 0
  pat = re.compile(r'^\.text.(.+)$')
  for section in text_sections:
    mat = pat.match(section.name)
    if mat:
      name = DemangleName(mat.group(1))
    else:
      name = section.name
    print '  {0}: {1}'.format(name, section.size)
    size_sum += section.size

  print 'Total text size: {0}'.format(size_sum)

if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
