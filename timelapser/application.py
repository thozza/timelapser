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
import time
import datetime
import schedule
import yaml

from timelapser.cameras import CameraDevice


logger = logging.getLogger(__file__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


def take_picture(config, camera):
    if not config.should_run_now():
        return
    logger.info("Taking picture in %s ...", threading.current_thread())
    camera.set_capture_target(CameraDevice.CAPTURE_TARGET_MEMORY_CARD)
    picture = camera.take_picture()
    store_path = os.path.join(config.store_path, os.path.basename(picture))
    camera.download_picture(picture, store_path, config.keep_on_camera)
    logger.info("Stored taken picture in %s", store_path)


class TimelapseConfig(object):
    WEEK_DAYS = 'week_days'
    SINCE_TOD = 'since_tod'
    TILL_TOD = 'till_tod'
    FREQUENCY = 'frequency'
    CAMERA_ID = 'camera_id'
    KEEP_ON_CAMERA = 'keep_on_camera'
    STORE_PATH = 'store_path'

    DEFAULT_TIMELAPSE_CONFIG = {
        'week_days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'since_tod': {
            'hour': 0,
            'minute': 0,
            'second': 0
        },
        'till_tod': {
            'hour': 23,
            'minute': 59,
            'second': 59
        },
        'frequency': 10,
        'keep_on_camera': True,
        'store_path': os.path.join(os.getcwd(), 'timelapser_store')
    }

    def __init__(self, name, config_dict):
        self.name = name
        # First use default values
        self.initialize_from_dict(self.DEFAULT_TIMELAPSE_CONFIG)
        # Now override them with explicit values
        self.initialize_from_dict(config_dict)
        # TODO: move this to a better location
        if not os.path.isdir(self.store_path):
            os.makedirs(self.store_path)

    def __str__(self):
        return "<TimelapseConfig(name={} week_days={} since_tod={} till_tod={} frequency={} keep_on_camera={} " \
               "store_path={})>".format(
                self.name,
                self.week_days,
                self.since_tod,
                self.till_tod,
                self.frequency,
                self.keep_on_camera,
                self.store_path
                )

    def initialize_from_dict(self, config_dict):
        """
        Initialize the instance attributes from a given dictionary.

        :param config_dict:
        :return:
        """
        weekday_map = {
            'mon': 0,
            'tue': 1,
            'wed': 2,
            'thu': 3,
            'fri': 4,
            'sat': 5,
            'sun': 6
        }

        for key in [self.WEEK_DAYS, self.SINCE_TOD, self.TILL_TOD, self.FREQUENCY, self.CAMERA_ID,
                    self.KEEP_ON_CAMERA, self.STORE_PATH]:
            try:
                # store Time Of Day as datetime.time object for convenience
                if key in [self.SINCE_TOD, self.TILL_TOD]:
                    time_dict = config_dict[key]
                    value = datetime.time(
                        hour=time_dict.get('hour', 0),
                        minute=time_dict.get('minute', 0),
                        second=time_dict.get('second', 0)
                    )
                # store week days as numbers
                elif key == self.WEEK_DAYS:
                    weekdays = config_dict[key]
                    value = [weekday_map[k.lower()] for k in weekdays]
                # rest of the values are used as they are
                else:
                    value = config_dict[key]

                self.__setattr__(key, value)
            except KeyError:
                continue

    def should_run_now(self, time_now=None):
        """
        Function which determines whether the timelapse job should be run NOW?

        :param time_now: Time determining what it means NOW.
        :return: True if yes, False otherwise.
        """
        if time_now is None:
            time_now = datetime.datetime.now()

        def time_in_range(start, end, now):
            """
            Returns True if 'now' is in the range of 'start' and 'end'. False otherwise
            """
            if start <= end:
                return start <= now <= end
            else:
                return start <= now or now <= end

        # First check day of the week
        if time_now.weekday() not in self.week_days:
            logger.debug("TimelapseConfig(name=%s): not configured to run on this week day %d", self.name, time_now.weekday())
            return False

        # Now check the time of day
        if not time_in_range(self.since_tod, self.till_tod, time_now.time()):
            logger.debug("TimelapseConfig(name=%s): not configured to run at this time %s", self.name, time_now.time())
            return False

        return True

    @staticmethod
    def find_timelapser_configuration():
        config_file_name = 'timelapser.yml'
        paths = [
            # configuration in CWD
            os.path.join(os.getcwd(), config_file_name),
            # configuration in user's home
            os.path.expanduser(os.path.join('~', config_file_name)),
            # system-wide configuration
            os.path.join('etc', config_file_name)
        ]

        for path in paths:
            if os.path.isfile(path):
                logger.debug("Most preferred config file is '%s'", path)
                return path
        # TODO: probably return an Exception? we should probably use some default values in case no configurtation  was specified.
        return None

    @staticmethod
    def parse_configs_from_file(path=None):
        """
        Parse Timelapse Configurations from a passed YAML config file.

        :param path: Path to the configuration YAML file
        :return: list of TimelapseConfig objects.
        """
        # If no specific configuration was specified, just try to look for some
        if path is None:
            path = TimelapseConfig.find_timelapser_configuration()

        logger.debug("Using timelapser configuration file '%s'", path)
        with open(path) as config_file:
            configuration = yaml.safe_load(config_file)
            logger.debug("Configuration loaded from YMAL file: %s", str(configuration))

        configurations = list()
        for key, value in configuration.items():
            configurations.append(TimelapseConfig(key, value))
            logger.debug("Parsed Timelapse Config: %s", str(configurations[-1]))
        return configurations


class Application(object):

    def __init__(self, options):
        self.cli_options = self.get_argparser().parse_args(options)
        logger.debug("Parsed CLI options: %s", self.cli_options)
        self.scheduler = schedule.Scheduler()
        self.camera_device_list = CameraDevice.get_available_cameras()
        self.timelapse_config_list = TimelapseConfig.parse_configs_from_file(self.cli_options.config)

    @staticmethod
    def get_argparser():
        parser = argparse.ArgumentParser()
        parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Use more verbose output.')
        parser.add_argument('-c', '--config', action='store', default=None, help='Path to configuration file to use.')
        return parser

    @staticmethod
    def run_threaded_job(job_func, timelapse_configuration, camera):
        if timelapse_configuration.should_run_now():
            logger.debug("Timelapse should run now, executing...")
            job_thread = threading.Thread(target=job_func, args=(timelapse_configuration, camera))
            job_thread.start()
        else:
            logger.debug("Timelapse is configured not to run at this time, skipping.")

    def schedule_timelapse(self, timelapse_config, camera):
        # TODO: it can happen that multiple threads access the same USB device at the same time and then it breaks
        #job = self.scheduler.every(timelapse_config.frequency).seconds.do(Application.run_threaded_job, take_picture, timelapse_config, camera)
        # TODO try to change scheduler, as even thought the picture should be taken every 5s, it is 8s
        job = self.scheduler.every(timelapse_config.frequency).seconds.do(take_picture, timelapse_config, camera)
        job.tag(timelapse_config)
        job.tag(camera)

    def run(self):
        # for now, just take the first config and first camera
        config = self.timelapse_config_list[0]
        camera = self.camera_device_list[0]
        self.schedule_timelapse(config, camera)

        while True:
            self.scheduler.run_pending()
            time.sleep(1)


def main(options=None):
    """
    Main function.

    :param options: command line options
    :return: None
    """
    try:
        # Do this as the first thing, so that we don't miss any debug log
        if Application.get_argparser().parse_args(options).verbose:
            logger.setLevel(logging.DEBUG)

        app = Application(options)
        app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by the user.")
        sys.exit(0)
    except Exception as e:
        logger.critical("Unexpected error occurred: %s", str(e))
        sys.exit(1)
    else:
        sys.exit(0)


def run_main():
    main(sys.argv[1:])
