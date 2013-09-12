#!/usr/bin/python

#
# Copyright 2013 Google Inc. All Rights Reserved.
"""Library to invoke readelf and parse its output.

Readelf itself has various options. The purpose of this module is to wrap it
with easy to use APIs.

One example usage of this library is to get the size of executable sections
(and used later for sorting/comparing by another script) -

  text_size = 0
  elf_reader = ElfReader('WebKit/MatchedPropertiesCache.o')
  for sec in elf_reader.ReadSections(True):
    text_size = text_size + sec.size

This version currently only implements 'read section information' and 'read elf
header information'. More will be added later.
"""

__author__ = ('shenhan@google.com (Han Shen)')

import re
import sys

from utils import command_executer


class ElfHeader(object):
  """Elf Header container.

  Access each header tag like this -
    elfheader._class
    elfheader._number_of_program_headers
    elfheader._machine
    ...
  Not all tags are presented here, but it's extremely easy to add.
  """
  # Tag names as is displayed by "realelf -h".
  TAG_NAMES = ['Class', 'Data', 'Machine', 'Version', 'Size of this header',
               'Number of program headers', 'Flags']

  # Class property names presenting tag names.
  PROPERTIES_NAMES = [x.lower().replace(' ', '_').replace('/', '_') for x
                      in TAG_NAMES]

  # Tag regular expression patterns, used only in parsing.
  PROPERTIES_PATTERNS = [re.compile(
      r'^\s+{0}:\s+([^\s].*)$'.format(x)) for x in TAG_NAMES]

  def __init__(self):
    for p in ElfHeader.PROPERTIES_NAMES:
      self.__dict__[p] = None

  def __repr__(self):
    r = ['{']
    for t, p in zip(ElfHeader.TAG_NAMES, ElfHeader.PROPERTIES_NAMES):
      r.append('{0}: {1}'.format(t, self.__dict__[p]))
    r.append('}')
    return '\n  '.join(r)


class ElfSection(object):

  """Elf section containuer.
  """

  def __init__(self):
    self.id = None
    self.name = None
    self.type = None
    self.address = None
    self.offset = None
    self.size = None
    self.flags = None

  def __repr__(self):
    return ('{{id: {0}\n  name: {1}\n  type={2}\n  address={3}\n  offset={4}\n'
            '  size={5}\n  flags={6}\n}}\n').format(
                self.id, self.name, self.type, self.address,
                self.offset, self.size, self.flags)


class ReadElf(object):
  """Main entry for this library.
  """

  def __init__(self, filename_):
    self.filename = filename_

  def ReadHeader(self, tagszip=zip(
      ElfHeader.PROPERTIES_NAMES, ElfHeader.PROPERTIES_PATTERNS)):
    """Read header tag values.

    Args:
      tagszip: a tuple of pairs that specify which values
          are required to capture.
    Returns:
      A list of ElfHeader obejcts.
    """

    cexec = command_executer.GetCommandExecuter()
    cmd = 'readelf -h {0}'.format(self.filename)
    (ec, output, _) = cexec.RunCommand(
        cmd, return_output=True, print_to_console=False)
    if ec == 0:
      header = ElfHeader()
      lines = output.splitlines()
      for l in lines:
        for pn, pp in tagszip:
          mo = pp.match(l)
          if mo:
            header.__dict__[pn] = mo.group(1)
            break
      # End of iterating all headers.
      return header
    return None

  def ReadHeaderTag(self, tagname):
    for tn, pn, pp in zip(ElfHeader.TAG_NAMES,
                          ElfHeader.PROPERTIES_NAMES,
                          ElfHeader.PROPERTIES_PATTERNS):
      if tn == tagname:
        header = self.ReadHeader(zip([pn], [pp]))
        if header:
          return header.__dict__[pn]
        return None
    return None

  def ReadSections(self, exec_sections_only=False):
    """Read all the sections.

    Args:
      exec_sections_only: whether to only inlcude executable section.
    Returns:
      A list of ElfSection objects.
    """
    cexec = command_executer.GetCommandExecuter()
    cmd = 'readelf -S -t {0}'.format(self.filename)
    (ec, output, _) = cexec.RunCommand(
        cmd, return_output=True, print_to_console=False)
    if ec != 0:
      return None

    sections = []

    ## Analyze these lines (for 32-bit)
      # [ 0]
      #      NULL            00000000 000000 000000 00   0   0  0
      #      [00000000]:
      # [ 1] .group
      #      GROUP           00000000 000034 000008 04  74  78  4
      #      [00000000]:

    ## or these lines (for 64-bit)
      # [ 0]
      #      NULL             0000000000000000  0000000000000000  0
      #      0000000000000000 0000000000000000  0                 0
      #      [0000000000000000]:
      # [ 1] .text
      #      PROGBITS         0000000000000000  0000000000000040  0
      #      0000000000000059 0000000000000000  0                 4
      #      [0000000000000006]: ALLOC, EXEC
    section_start = re.compile(r'\s*\[\s*(\d+)\]\s*([^\s]*)\s*$')
    lines = output.splitlines()
    current_section = None
    section_part = 0
    for l in lines:
      if section_part == 0:
        section_start_mo = section_start.match(l)
        if section_start_mo:
          current_section = ElfSection()
          current_section.id = int(section_start_mo.group(1))
          current_section.name = section_start_mo.group(2)
          section_part = 1
          continue

      if section_part == 1:
        ss = l.strip().split()
        current_section.type = ss[0]
        current_section.address = int(float.fromhex(ss[1]))
        current_section.offset = int(float.fromhex(ss[2]))
        if len(ss) == 8:
          current_section.size = int(float.fromhex(ss[3]))
          section_part = 3
        else:
          section_part = 2
        continue

      if section_part == 2:
        ss = l.strip().split()
        current_section.size = int(float.fromhex(ss[0]))
        section_part = 3
        continue

      if section_part == 3:
        current_section.flags = l.strip()
        if not exec_sections_only or current_section.flags.find('EXEC') > -1:
          sections.append(current_section)
        current_section = None
        section_part = 0
        continue

    return sections


def Main(args):
  elf = ReadElf(args[1])
  print elf.ReadHeader()
  print elf.ReadSections()
  return 0

if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
