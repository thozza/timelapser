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

from timelapser.log import log


class TimelapseConfigTrigger(BaseTrigger):

    def __init__(self, timelapse_config):
        self._timelapse_config = timelapse_config

    def get_next_fire_time(self, previous_fire_time, now):
        """
        Returns the next datetime to fire on, If no such datetime can be calculated, returns None.
        """
        # TODO: Take "now" parameter into account when calculating the next run. Especially make sure that "next_time > now"
        # The job is being scheduled for the first time
        if not previous_fire_time:
            previous_fire_time = now

        delta = datetime.timedelta(seconds=self._timelapse_config.frequency)
        next_time = previous_fire_time + delta

        # modify the time until it fits the criteria
        if not self._timelapse_config.should_run_now(next_time):
            # There was an error, that made the next_time be scheduled for the same day, but in the past, because the current day
            # fit the configured weekdays but it was past till_tod. This happened when since_tod < till_tod. In this case we need
            # to jump one day into the future, but before since_tod, so using 00:00.00!
            if self._timelapse_config.since_tod < self._timelapse_config.till_tod < next_time.time():
                next_time = datetime.datetime.combine(next_time.date() + datetime.timedelta(days=1), datetime.time())

            # first get through the day of week
            while next_time.weekday() not in self._timelapse_config.week_days:
                next_time = datetime.datetime.combine(next_time.date() + datetime.timedelta(days=1), next_time.timetz())

            # now fix the time
            next_time = datetime.datetime.combine(
                next_time.date(),
                self._timelapse_config.since_tod,
                tzinfo=next_time.tzinfo
            )
            log.debug("Next job scheduled for %s", next_time.strftime("%c"))
        return next_time
