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
import tzlocal

import pytest

from timelapser.configuration import TimelapseConfig
from timelapser.scheduler import TimelapseConfigTrigger


@pytest.fixture
def make_timelapse_config():

    def _make_timelapse_config(since_tod, till_tod, weekdays):
        conf_dict = {
            TimelapseConfig.SINCE_TOD: {
                "hour": since_tod.hour,
                "minute": since_tod.minute,
                "second": since_tod.second
            },
            TimelapseConfig.TILL_TOD: {
                "hour": till_tod.hour,
                "minute": till_tod.minute,
                "second": till_tod.second
            },
            TimelapseConfig.WEEK_DAYS: weekdays,
        }
        return TimelapseConfig(conf_dict)

    return _make_timelapse_config


class TestTimelapseConfigTrigger:

    # dates which can be used for configuration
    # Mon 15.10.2018
    # Tue 16.10.2018
    # Wed 17.10.2018
    # Thu 18.10.2018
    # Fri 19.10.2018
    # Sat 20.10.2018
    # Sun 21.10.2018
    # --------------
    # Mon 22.10.2018
    # Tue 23.10.2018

    @staticmethod
    def test_get_next_fire_time_since_before_till(make_timelapse_config):
        configration = make_timelapse_config(
            since_tod=datetime.time(10, 30, 0),
            till_tod=datetime.time(22, 0, 0),
            weekdays=["Tue", "Wed", "Thu"]
        )
        trigger = TimelapseConfigTrigger(configration)

        # last execution was day before the allowed window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 15, 7, 0, 0), None) == datetime.datetime(2018, 10, 16, 10, 30, 0)
        # last execution the same day, but earlier
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 7, 0, 0), None) == datetime.datetime(2018, 10, 16, 10, 30, 0)
        # last execution right at the start
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 10, 30, 0), None) == datetime.datetime(2018, 10, 16, 10, 30,
                                                                                                                 0 + configration.frequency)
        # last execution is within the allowed range
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 12, 0, 0), None) == datetime.datetime(2018, 10, 16, 12, 0,
                                                                                                                0 + configration.frequency)
        # last execution is at the end of window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 22, 0, 0), None) == datetime.datetime(2018, 10, 17, 10, 30, 0)
        # last execution way after the end of window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 23, 0, 0), None) == datetime.datetime(2018, 10, 17, 10, 30, 0)
        # last execution day after allowed window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 19, 12, 0, 0), None) == datetime.datetime(2018, 10, 23, 10, 30, 0)

    @staticmethod
    def test_get_next_fire_time_since_after_till(make_timelapse_config):
        configration = make_timelapse_config(
            since_tod=datetime.time(22, 0, 0),
            till_tod=datetime.time(10, 30, 0),
            weekdays=["Tue", "Wed", "Thu"]
        )
        trigger = TimelapseConfigTrigger(configration)

        # last execution was day before the allowed window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 15, 7, 0, 0), None) == datetime.datetime(2018, 10, 16, 22, 0, 0)
        # last execution the same day, but earlier
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 12, 0, 0), None) == datetime.datetime(2018, 10, 16, 22, 0, 0)
        # last execution right at the start
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 22, 0, 0), None) == datetime.datetime(2018, 10, 16, 22, 0,
                                                                                                                0 + configration.frequency)
        # last execution is within the allowed range
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 22, 30, 0), None) == datetime.datetime(2018, 10, 16, 22, 30,
                                                                                                                 0 + configration.frequency)
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 17, 9, 30, 0), None) == datetime.datetime(2018, 10, 17, 9, 30,
                                                                                                                0 + configration.frequency)
        # last execution is at the end of window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 10, 30, 0), None) == datetime.datetime(2018, 10, 16, 22, 0, 0)
        # last execution way after the end of window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 11, 0, 0), None) == datetime.datetime(2018, 10, 16, 22, 0, 0)
        # last execution day after allowed window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 19, 12, 0, 0), None) == datetime.datetime(2018, 10, 23, 22, 0, 0)

    @staticmethod
    def test_get_next_fire_time_tzinfo_preservation(make_timelapse_config):
        configration = make_timelapse_config(
            since_tod=datetime.time(10, 30, 0),
            till_tod=datetime.time(22, 0, 0),
            weekdays=["Tue", "Wed", "Thu"]
        )
        trigger = TimelapseConfigTrigger(configration)

        # last execution was day before the allowed window
        # the point is that the returned datetime.datetime must have tzinfo, if it had initially
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 15, 7, 0, 0,
                                                            tzinfo=tzlocal.get_localzone()),
                                          None) == datetime.datetime(2018, 10, 16, 10, 30, 0,
                                                                     tzinfo=tzlocal.get_localzone())
        # last execution is at the end of window
        assert trigger.get_next_fire_time(datetime.datetime(2018, 10, 16, 22, 0, 0,
                                                            tzinfo=tzlocal.get_localzone()),
                                          None) == datetime.datetime(2018, 10, 17, 10, 30, 0,
                                                                     tzinfo=tzlocal.get_localzone())
