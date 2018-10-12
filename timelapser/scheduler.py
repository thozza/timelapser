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

from apscheduler.triggers.base import BaseTrigger

from timelapser.logging import log


class TimelapseConfigTrigger(BaseTrigger):

    def __init__(self, timelapse_config):
        self._timelapse_config = timelapse_config

    def get_next_fire_time(self, previous_fire_time, now):
        """
        Returns the next datetime to fire on, If no such datetime can be calculated, returns None.
        """
        # The job is being scheduled for the first time
        if previous_fire_time is None:
            previous_fire_time = datetime.datetime.now()

        delta = datetime.timedelta(seconds=self._timelapse_config.frequency)
        next_time = previous_fire_time + delta

        # modify the time until it fits the criteria
        if not self._timelapse_config.should_run_now(next_time):
            # first get through the day of week
            while next_time.weekday() not in self._timelapse_config.week_days:
                next_time = datetime.datetime.combine(next_time.date() + datetime.timedelta(days=1), next_time.timetz())

            # now fix the time
            # TODO: Verify that this actually works correctly when we passed till_tod and changed the day
            next_time = datetime.datetime.combine(
                next_time.date(),
                self._timelapse_config.since_tod,
                tzinfo=next_time.tzinfo
            )
            log.debug("Next job scheduled for %s", next_time.strftime("%c"))
        return next_time
