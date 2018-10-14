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

import os
import sys
import argparse
import logging
import threading

from apscheduler.schedulers.blocking import BlockingScheduler

from timelapser.configuration import TimelapseConfig
from timelapser.scheduler import TimelapseConfigTrigger
from timelapser.logging import log
from timelapser.cameras import CameraDevice


def take_picture(config, camera):
    log.info("Taking picture in %s ...", threading.current_thread())
    camera.set_capture_target(CameraDevice.CAPTURE_TARGET_MEMORY_CARD)
    picture = camera.take_picture()
    store_path = os.path.join(config.store_path, os.path.basename(picture))
    camera.download_picture(picture, store_path, config.keep_on_camera)
    log.info("Stored taken picture in %s", store_path)


class Application(object):

    def __init__(self, options):
        self.cli_options = self.get_argparser().parse_args(options)
        log.debug("Parsed CLI options: %s", self.cli_options)
        self.scheduler = BlockingScheduler()
        self.camera_device_list = CameraDevice.get_available_cameras()
        self.timelapse_config_list = TimelapseConfig.parse_configs_from_file(self.cli_options.config)

    @staticmethod
    def get_argparser():
        parser = argparse.ArgumentParser()
        parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Use more verbose output.')
        parser.add_argument('-c', '--config', action='store', default=None, help='Path to configuration YAML file \
        to use.')
        return parser

    def schedule_timelapse(self, timelapse_config, camera):
        # TODO: it can happen that multiple threads access the same USB device at the same time and then it breaks
        job = self.scheduler.add_job(take_picture, TimelapseConfigTrigger(timelapse_config), args=(timelapse_config, camera))

    def stop(self):
        log.info("Shutting down the application")
        self.scheduler.shutdown()

    def run(self):
        # for now, just take the first config and first camera
        config = self.timelapse_config_list[0]
        camera = self.camera_device_list[0]
        self.schedule_timelapse(config, camera)

        self.scheduler.start()


def main(options=None):
    """
    Main function.

    :param options: command line options
    :return: None
    """
    app = None
    try:
        # Do this as the first thing, so that we don't miss any debug log
        if Application.get_argparser().parse_args(options).verbose:
            log.setLevel(logging.DEBUG)

        app = Application(options)
        app.run()
    except KeyboardInterrupt:
        log.info("Application interrupted by the user.")
        if app is not None:
            app.stop()
        sys.exit(0)
    #except Exception as e:
    #    logger.critical("Unexpected error occurred: %s", str(e))
    #    sys.exit(1)
    else:
        sys.exit(0)


def run_main():
    main(sys.argv[1:])
