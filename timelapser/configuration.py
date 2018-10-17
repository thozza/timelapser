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

import datetime
import os

import yaml

from timelapser.log import log


class TimelapseConfigError(Exception):
    pass


class TimelapseConfig(object):
    WEEK_DAYS = 'week_days'
    SINCE_TOD = 'since_tod'
    TILL_TOD = 'till_tod'
    FREQUENCY = 'frequency'
    CAMERA_SN = 'camera_sn'
    KEEP_ON_CAMERA = 'keep_on_camera'

    DATASTORE = 'datastore'
    DATASTORE_TYPE = 'type'
    DATASTORE_STORE_PATH = 'store_path'
    DATASTORE_DROPBOX_TOKEN = 'dropbox_token'

    DATASTORE_TYPE_FILESYSTEM = 'filesystem'
    DATASTORE_TYPE_DROPBOX = 'dropbox'
    DATASTORE_TYPES = [
        DATASTORE_TYPE_FILESYSTEM,
        DATASTORE_TYPE_DROPBOX
    ]

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
        'camera_sn': '',
        'keep_on_camera': True,
        'datastore': [
            {
                'type': 'filesystem',
                'store_path': os.path.join(os.getcwd(), 'timelapser_store'),
            },
        ]
    }

    def __init__(self, config_dict=None):
        # First use default values
        self.initialize_from_dict(self.DEFAULT_TIMELAPSE_CONFIG)

        if config_dict is not None:
            # Now override them with explicit values
            self.initialize_from_dict(config_dict)

    def __str__(self):
        # TODO: Add also datastore info, but make sure to not leak any token to logs
        return "<TimelapseConfig(id={} week_days={} since_tod={} till_tod={} frequency={} keep_on_camera={})>".format(
                id(self),
                self.week_days,
                self.since_tod,
                self.till_tod,
                self.frequency,
                self.keep_on_camera,
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

        for key in [self.WEEK_DAYS, self.SINCE_TOD, self.TILL_TOD, self.FREQUENCY, self.CAMERA_SN,
                    self.KEEP_ON_CAMERA, self.DATASTORE]:
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

                elif key == self.DATASTORE:
                    datastores = config_dict[key]
                    # make sure there is always a list of datastores, but allow users to specify just one as a dict
                    if isinstance(datastores, dict):
                        datastore = datastores
                        datastores = list()
                        datastores.append(datastore)
                    # validate datastores configuration
                    for datastore in datastores:
                        try:
                            datastore_type = datastore[self.DATASTORE_TYPE]
                        except KeyError:
                            raise TimelapseConfigError("datastore must have a 'type' defined")
                        if datastore_type not in self.DATASTORE_TYPES:
                            raise TimelapseConfigError("datastore 'type' configuration value must be one of %s",
                                                       self.DATASTORE_TYPES)
                        try:
                            datastore[self.DATASTORE_STORE_PATH]
                        except KeyError:
                            raise TimelapseConfigError("datastore must have a 'store_path' defined")
                        if datastore_type == self.DATASTORE_TYPE_DROPBOX:
                            try:
                                datastore[self.DATASTORE_DROPBOX_TOKEN]
                            except KeyError:
                                raise TimelapseConfigError("datastore type 'dropbox' must have a 'dropbox_token' "
                                                           "defined")
                    value = datastores

                # rest of the values are used as they are
                else:
                    value = config_dict[key]

                self.__setattr__(key, value)
            except KeyError:
                continue

        # TODO: check that at least one datastore is specified

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
            log.debug("%s: not configured to run on this week day %d", self, time_now.weekday())
            return False

        # Now check the time of day
        if not time_in_range(self.since_tod, self.till_tod, time_now.time()):
            log.debug("%s: not configured to run at this time %s", self, time_now.time())
            return False

        return True

    @staticmethod
    def find_timelapser_configuration():
        config_file_name = 'timelapser.yaml'
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
                log.debug("Most preferred config file is '%s'", path)
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

        # didn't find any configuration file in default locations
        if path is None:
            log.info("Didn't find any configuration file.")
            parsed_configs = None
        else:
            log.debug("Using timelapser configuration file '%s'", path)
            with open(path) as config_file:
                configuration = yaml.safe_load(config_file)
                log.debug("Configuration loaded from YMAL file: %s", str(configuration))

            parsed_configs = configuration.get("timelapse_configuration", None)

        configurations = list()
        if parsed_configs is not None:
            for config in parsed_configs:
                configurations.append(TimelapseConfig(config))
                log.debug("Parsed Timelapse Config: %s", str(configurations[-1]))
        else:
            # no confurations found, go just with default one
            configurations.append(TimelapseConfig())
            log.info("Didn't find any explicit timelapse configuration. Using default values.")

        return configurations