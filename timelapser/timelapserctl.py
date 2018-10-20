#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2018 Tomas Hozza
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
import argparse
import logging

from timelapser.configuration import TimelapseConfig, TimelapseConfigError
from timelapser.log import log
from timelapser.cameras import CameraDevice


class TimelapserCtl(object):

    def __init__(self, options):
        self.cli_options = self.get_argparser().parse_args(options)
        log.debug("Parsed CLI options: %s", self.cli_options)

    @staticmethod
    def get_argparser():
        parser = argparse.ArgumentParser()
        parser.add_argument("-v", "--verbose", action="store_true", default=False, help="Use more verbose output.")

        subparsers = parser.add_subparsers(dest='command', help="commands help")
        subparsers.required = True

        parser_lc = subparsers.add_parser("list-cameras", help="List available cameras on the system")
        parser_lc.set_defaults(func=TimelapserCtl.command_list_cameras)

        parser_cc = subparsers.add_parser("check-conf", help="Check validity of given configuration")
        parser_cc.add_argument(
            "config",
            metavar='CONFIG',
            help="Configuration file to check. If not specified, the preferred configuration is checked.",
            default=None,
            nargs='?'
        )
        parser_cc.set_defaults(func=TimelapserCtl.command_check_conf)

        return parser

    @staticmethod
    def command_list_cameras(options):
        cameras = CameraDevice.get_available_cameras()
        if not cameras:
            print("No available cameras found on the system!")
            return
        else:
            print("Found {} available cameras:".format(len(cameras)))

        for camera in cameras:
            print("{}\tSN: {}".format(camera.name, camera.serial_number))

    @staticmethod
    def command_check_conf(options):
        config_file = options.config
        if not config_file:
            log.info("No configuration file passed, checking validity of the most preferred configuration file.")
            config_file = TimelapseConfig.find_timelapser_configuration()
        if not config_file:
            log.error("No configuration file found in preferred locations.")
        else:
            print("Checking validity of '{}'".format(config_file))
            try:
                configs = TimelapseConfig.parse_configs_from_file(config_file)
            except TimelapseConfigError as err:
                print("Configuration is not valid. Found following error:\n{}".format(err))
                return 1
            except FileNotFoundError as err:
                print("Configuration file not found!")
                return 1
            else:
                print("Configuration is valid!")
                for config in configs:
                    print(config)
                    print(config.datastore)

    def run_command(self):
        return self.cli_options.func(self.cli_options)


def main(options=None):
    """
    Main function.

    :param options: command line options
    :return: None
    """
    try:
        # Do this as the first thing, so that we don't miss any debug log
        if TimelapserCtl.get_argparser().parse_args(options).verbose:
            log.setLevel(logging.DEBUG)
        app = TimelapserCtl(options)
        ret = app.run_command()
    except KeyboardInterrupt:
        log.info("Application interrupted by the user.")
        sys.exit(0)
    #except Exception as e:
    #    logger.critical("Unexpected error occurred: %s", str(e))
    #    sys.exit(1)
    else:
        sys.exit(ret)


def run_main():
    main(sys.argv[1:])
