#!/usr/bin/python

# Copyright 2014 Google Inc. All Rights Reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time
import urllib2

from utils import command_executer
from utils import logger
from utils import buildbot_json

SLEEP_TIME = 600  # 10 minutes; time between polling of buildbot.
TIME_OUT =  18000 # Decide the build is dead or will never finish
                  # after this time (5 hours).

"""Utilities for launching and accessing ChromeOS buildbots."""

def ParseReportLog (url, build):
    """
    Scrape the trybot image name off the Reports log page.

    This takes the URL for a trybot Reports Stage web page,
    and a trybot build type, such as 'daisy-release'.  It
    opens the web page and parses it looking for the trybot
    artifact name (e.g. something like
    'trybot-daisy-release/R40-6394.0.0-b1389'). It returns the
    artifact name, if found.
    """
    trybot_image = ""
    url += "/text"
    newurl = url.replace ("uberchromegw", "chromegw")
    webpage = urllib2.urlopen(newurl)
    data = webpage.read()
    lines = data.split('\n')
    for l in lines:
      if l.find("Artifacts") > 0 and l.find("trybot") > 0:
        trybot_name = "trybot-%s" % build
        start_pos = l.find(trybot_name)
        end_pos = l.find("@https://storage")
        trybot_image = l[start_pos:end_pos]

    return trybot_image

def GetBuildData (buildbot_queue, build_id):
    """
    Find the Reports stage web page for a trybot build.

    This takes the name of a buildbot_queue, such as 'daisy-release'
    and a build id (the build number), and uses the json buildbot api to
    find the Reports stage web page for that build, if it exists.
    """
    builder = buildbot_json.Buildbot(
      "http://chromegw/p/tryserver.chromiumos/").builders[buildbot_queue]
    build_data = builder.builds[build_id].data
    logs = build_data["logs"]
    for l in logs:
      fname = l[1]
      if "steps/Report/" in fname:
        return fname

    return ""


def FindBuildRecordFromLog(description, log_info):
    """
    Find the right build record in the build logs.

    Get the first build record from build log with a reason field
    that matches 'description'. ('description' is a special tag we
    created when we launched the buildbot, so we could find it at this
    point.)
    """

    current_line = 1
    while current_line < len(log_info):
      my_dict = {}
      # Read all the lines from one "Build" to the next into my_dict
      while True:
        key = log_info[current_line].split(":")[0].strip()
        value = log_info[current_line].split(":", 1)[1].strip()
        my_dict[key] = value
        current_line += 1
        if "Build" in key or current_line == len(log_info):
          break
      try:
        # Check to see of the build record is the right one.
        print("(shenhan): A - {}, B - {}".format(
          str(description), my_dict["reason"]))
        if str(description) in my_dict["reason"]:
          # We found a match; we're done.
          return my_dict
      except:
        print "reason is not in dictionary: '%s'" % repr(my_dict)
      else:
        # Keep going.
        continue

    # We hit the bottom of the log without a match.
    return {}

def GetBuildRecord(file_dir, reason_to_find):
    commands = ("{0}/utils/buildbot_json.py builds "
                "https://chromegw/i/tryserver.chromiumos/"
                .format(file_dir))
    ce = command_executer.GetCommandExecuter()
    class BuildRecordConsumer(object):

        def __init__(self, reason):
            self.record_dict = {}
            self.reason = reason
            self.record_found = None

        def consume(self, line, output, pobject):
            if line.startswith("Build:"):
                print("(shenhan): consumer found one record.")
                if ('reason' in self.record_dict and
                    self.reason in self.record_dict['reason']):
                    self.record_found = self.record_dict
                    print("(shenhan): found record \"{}\"".format(self.reason))
                    pobject.kill()
                self.record_dict = {}
            else:
                line = line.strip()
                segs = line.split(":", 1)
                if len(segs) >= 2:
                    key, value = segs
                    self.record_dict[key] = value

    consumer = BuildRecordConsumer(reason_to_find)
    ce.RunCommand2(commands, cwd=None, line_consumer=consumer.consume,
                   timeout=60 * 30, join_stderr=False, env=None)
    # Ignore return value, just check if we found the record.
    if consumer.record_found:
        return consumer.record_found
    return {}


def GetBuildInfo(file_dir, builder):
    """
    Get all the build records for the trybot builds.

    file_dir is the toolchain_utils directory.
    """
    ce = command_executer.GetCommandExecuter()
    commands = ("{0}/utils/buildbot_json.py builds "
                "http://chromegw/i/tryserver.chromiumos/"
                .format(file_dir))

    if builder:
      commands += " -b %s" % builder
    _, buildinfo, _ = ce.RunCommand(commands, return_output=True,
                                    print_to_console=False)
    build_log = buildinfo.splitlines()
    return build_log


def FindArchiveImage(chromeos_root, build, build_id):
    """
    Given a build_id, search Google Storage for a trybot artifact
    for the correct board with the correct build_id.  Return the
    name of the artifact, if found.
    """
    ce = command_executer.GetCommandExecuter()
    command = ("gsutil ls gs://chromeos-image-archive/trybot-%s/*b%s"
               "/chromiumos_test_image.tar.xz" % (build, build_id))
    retval, out, err = ce.ChrootRunCommand(chromeos_root, command,
                                           return_output=True,
                                           print_to_console=False)

    trybot_image = ""
    trybot_name = "trybot-%s" % build
    if out and out.find(trybot_name) > 0:
        start_pos = out.find(trybot_name)
        end_pos = out.find("/chromiumos_test_image")
        trybot_image = out[start_pos:end_pos]

    return trybot_image

def GetTrybotImage(chromeos_root, buildbot_name, patch_list, build_tag,
                   build_toolchain=False):
    """
    Launch buildbot and get resulting trybot artifact name.

    This function launches a buildbot with the appropriate flags to
    build the test ChromeOS image, with the current ToT mobile compiler.  It
    checks every 10 minutes to see if the trybot has finished.  When the trybot
    has finished, it parses the resulting report logs to find the trybot
    artifact (if one was created), and returns that artifact name.

    chromeos_root is the path to the ChromeOS root, needed for finding chromite
    and launching the buildbot.

    buildbot_name is the name of the buildbot queue, such as lumpy-release or
    daisy-paladin.

    patch_list a python list of the patches, if any, for the buildbot to use.

    build_tag is a (unique) string to be used to look up the buildbot results
    from among all the build records.
    """
    ce = command_executer.GetCommandExecuter()
    cbuildbot_path = os.path.join(chromeos_root, "chromite/cbuildbot")
    base_dir = os.getcwd()
    patch_arg = ""
    if patch_list:
      patch_arg = "-g "
      for p in patch_list:
        patch_arg = patch_arg + " " + repr(p)
    toolchain_flags=""
    if build_toolchain:
      toolchain_flags += "--latest-toolchain"
    branch = "master"
    os.chdir(cbuildbot_path)

    # Launch buildbot with appropriate flags.
    build = buildbot_name
    description = build_tag
    command = ("./cbuildbot --remote --nochromesdk --notests"
               " --remote-description=%s %s %s %s"
               % (description, toolchain_flags, patch_arg, build))
    _, out, _ = ce.RunCommand(command, return_output=True)
    if "Tryjob submitted!" not in out:
      logger.GetLogger().LogFatal("Error occurred while launching trybot job: "
                                  "%s" % command)
    os.chdir(base_dir)

    build_id = 0
    build_status = None
    # Wait for  buildbot to finish running (check every 10 minutes).  Wait
    # 10 minutes before the first check to give the buildbot time to launch
    # (so we don't start looking for build data before it's out there).
    print("(shenhan): about to sleep.")
    print("(shenhan): description: {}".format(description))
    time.sleep(200)
    done = False
    pending = True
    # pending_time is the time between when we submit the job and when the
    # buildbot actually launches the build.  running_time is the time between
    # when the buildbot job launches and when it finishes.  The job is
    # considered 'pending' until we can find an entry for it in the buildbot
    # logs.
    pending_time = SLEEP_TIME
    running_time = 0
    while not done:
      done = True
      build_info = GetBuildInfo(base_dir, build)
      if not build_info:
        if pending_time > TIME_OUT:
          logger.GetLogger().LogFatal("Unable to get build logs for target %s."
                                      % build)
        else:
          pending_message = "Unable to find build log; job may be pending."
          done = False

      if done:
        data_dict = FindBuildRecordFromLog(description, build_info)
        if not data_dict:
          # Trybot job may be pending (not actually launched yet).
          if pending_time > TIME_OUT:
            logger.GetLogger().LogFatal("Unable to find build record for trybot"
                                        " %s." % description)
          else:
            pending_message = "Unable to find build record; job may be pending."
            done = False

        else:
          # Now that we have actually found the entry for the build
          # job in the build log, we know the job is actually
          # runnning, not pending, so we flip the 'pending' flag.  We
          # still have to wait for the buildbot job to finish running
          # however.
          pending = False
          if "True" in data_dict["completed"]:
            build_id = data_dict["number"]
            build_status = int(data_dict["result"])
          else:
            done = False

        if not done:
          if pending:
            logger.GetLogger().LogOutput(pending_message)
            logger.GetLogger().LogOutput("Current pending time: %d minutes." %
                                         (pending_time / 60))
            pending_time  += SLEEP_TIME
          else:
            logger.GetLogger().LogOutput("{0} minutes passed.".format(
                running_time / 60))
            logger.GetLogger().LogOutput("Sleeping {0} seconds.".format(
                SLEEP_TIME))
            running_time += SLEEP_TIME

          time.sleep(SLEEP_TIME)
          if running_time > TIME_OUT:
            done = True

    trybot_image = FindArchiveImage(chromeos_root, build, build_id)
    if not trybot_image:
        logger.GetLogger().LogError("Trybot job %s failed with status %d;"
                                    " no trybot image generated."
                                    % (description, build_status))

    logger.GetLogger().LogOutput("trybot_image is '%s'" % trybot_image)
    logger.GetLogger().LogOutput("build_status is %d" % build_status)
    return trybot_image
