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
import asyncio
import argparse
import logging
import threading
import tempfile
import shutil

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from timelapser.configuration import TimelapseConfig
from timelapser.scheduler import TimelapseConfigTrigger
from timelapser.log import log
from timelapser.cameras import CameraDevice, CameraDeviceError
from timelapser.datastore import FilesystemDataStore, DropboxDataStore


class Application(object):

    def __init__(self, options):
        self.cli_options = self.get_argparser().parse_args(options)
        log.debug("Parsed CLI options: %s", self.cli_options)
        self.timelapse_config_list = TimelapseConfig.parse_configs_from_file(self.cli_options.config)
        self.scheduler = AsyncIOScheduler()
        self.active_cameras_sn = set()

    @staticmethod
    def get_argparser():
        parser = argparse.ArgumentParser()
        parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Use more verbose output.')
        parser.add_argument('-c', '--config', action='store', default=None, help='Path to configuration YAML file \
        to use.')
        return parser

    def _scheduler_add_job(self, config, camera):
        try:
            self.scheduler.add_jobstore(MemoryJobStore(), alias=camera.serial_number)
        except ValueError as e:
            raise e
        # TODO: It would probably make sense to make the number of max_instances configurable
        self.scheduler.add_job(
            self.take_picture_job,
            TimelapseConfigTrigger(config),
            args=(config, camera),
            jobstore=camera.serial_number,
            max_instances=2
        )
        self.active_cameras_sn.add(camera.serial_number)

    def _scheduler_remove_jobstore(self, jobstore):
        log.debug("Removing jobs for camera sn: %s", jobstore)
        self.scheduler.remove_jobstore(jobstore)
        self.active_cameras_sn.remove(jobstore)

    def refresh_timelapses_job(self):
        refresh_period = 5
        loop = asyncio.get_event_loop()

        available_cameras = CameraDevice.get_available_cameras()
        if len(available_cameras) == 0:
            log.debug("There are no available cameras, canceling any running jobs and will refresh in %d seconds",
                      refresh_period)
            for removed_camera_sn in self.active_cameras_sn:
                log.debug("Removing jobs for camera sn: %s", removed_camera_sn)
                self.scheduler.remove_jobstore(removed_camera_sn)
            self.active_cameras_sn.clear()
            self.scheduler.remove_all_jobs()
            loop.call_later(refresh_period, self.refresh_timelapses_job)
            return

        active_cameras_map = {c.serial_number: c for c in available_cameras}
        new_active_cameras_sn = [c.serial_number for c in available_cameras]
        # remove jobs and job stores for every removed camera
        removed_cameras_sn = self.active_cameras_sn - set(new_active_cameras_sn)
        for removed_camera_sn in removed_cameras_sn:
            self._scheduler_remove_jobstore(removed_camera_sn)

        new_cameras_sn = set(new_active_cameras_sn) - self.active_cameras_sn
        # Go through all configuration and add timelapse jobs for any new cameras that fit them
        for config in self.timelapse_config_list:
            camera_sn = config.camera_sn
            # the config is bound to specific device
            if camera_sn:
                if camera_sn in new_cameras_sn:
                    camera_device = active_cameras_map[camera_sn]
                    self._scheduler_add_job(config, camera_device)
                    log.debug("Added timelapse job for camera sn: %s", camera_sn)
            # configuration is not bound to specific device
            else:
                for camera_sn in new_cameras_sn:
                    camera_device = active_cameras_map[camera_sn]
                    self._scheduler_add_job(config, camera_device)
                    log.debug("Added timelapse job for camera sn: %s", camera_sn)

        loop.call_later(refresh_period, self.refresh_timelapses_job)

    def take_picture_job(self, config, camera):
        log.info("Taking picture in %s ...", threading.current_thread())
        tmp_store_dir = tempfile.mkdtemp()
        try:
            picture = camera.take_picture()
            tmp_store_location = os.path.join(tmp_store_dir, os.path.basename(picture))
            camera.download_picture(picture, tmp_store_location, config.keep_on_camera)
        except CameraDeviceError as err:
            # there is some problem with the Camera, remove its whole jobstore
            log.warning("Error occurred while taking picture on %s(%s)", camera.name, camera.serial_number)
            shutil.rmtree(tmp_store_dir)
            self._scheduler_remove_jobstore(camera.serial_number)
        else:
            log.info("Temporarily stored taken picture in %s", tmp_store_location)
            # TODO: think about scheduling this in a new thread, but it may be not necessary as the job itself runs in a dedicated thread
            # TODO: it may make sense to use camera_sn in the store path if the configuration is not bound to a specific camera, thus there can be multiple cameras storing pictures into the same folder
            self.store_tmp_file_in_datastore(config, tmp_store_location)

    @staticmethod
    def store_tmp_file_in_datastore(config, tmp_file):
        datastores = config.datastore

        for datastore in datastores:
            datastore_type = datastore[TimelapseConfig.DATASTORE_TYPE]

            if datastore_type == TimelapseConfig.DATASTORE_TYPE_DROPBOX:
                ds = DropboxDataStore(
                    datastore[TimelapseConfig.DATASTORE_DROPBOX_TOKEN],
                    datastore[TimelapseConfig.DATASTORE_STORE_PATH]
                )

            elif datastore_type == TimelapseConfig.DATASTORE_TYPE_FILESYSTEM:
                ds = FilesystemDataStore(datastore[TimelapseConfig.DATASTORE_STORE_PATH])

            else:
                raise NotImplemented("Unexpected datastore type '%s'", datastore_type)

            log.debug("Storing temporary file '%s' using data store '%s'", tmp_file, ds)
            ds.store_file(tmp_file, False)
        shutil.rmtree(os.path.dirname(tmp_file))

    def exception_handler_job(self, loop, context):
        log.critical("Unhandled exception happened in one of the callbacks, terminating the application!")
        log.exception(context['exception'])
        self.stop()

    def stop(self):
        log.info("Shutting down the application")
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown(wait=False)
        loop = asyncio.get_event_loop()
        loop.stop()

    def run(self):
        self.scheduler.start()
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(self.exception_handler_job)
        loop.call_soon(self.refresh_timelapses_job)
        loop.run_forever()
        loop.close()


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
