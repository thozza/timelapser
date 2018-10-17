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
import re
import threading

import gphoto2 as gp

from timelapser.log import log


class CameraDeviceBusy(Exception):
    pass


class CameraDeviceError(Exception):
    pass


class ThreadsafeCameraObject(gp.Camera):

    def __init__(self, *args, **kwargs):
        super(ThreadsafeCameraObject, self).__init__(*args, **kwargs)
        self._thread_lock = threading.Lock()

    def init(self, Context_context=None):
        self._thread_lock.acquire()
        try:
            return super(ThreadsafeCameraObject, self).init(Context_context)
        except gp.GPhoto2Error as err:
            self._thread_lock.release()
            #log.debug("Camera object init() error: (%d) %s", err.code, err)
            if err.code == -53:
                raise CameraDeviceBusy("Camera Device is busy. Make sure to close all other applications which may be "
                                       "using it")
            elif err.code == -2:
                raise CameraDeviceError("Error happened while trying to initialize the Camera Device.")

    def exit(self, Context_context=None):
        ret = super(ThreadsafeCameraObject, self).exit(Context_context)
        self._thread_lock.release()
        return ret


class CameraDevice(object):

    CAPTURE_TARGET_INTERNAL_RAM = 'Internal RAM'
    CAPTURE_TARGET_MEMORY_CARD = 'Memory card'

    camera_device_cache = dict()

    def __init__(self, device_name, device_address):
        self.address = device_address
        self.name = device_name
        self._camera_object = self._get_camera_object_by_addr(device_address)
        # TODO: Extend methods to work well regardless of the target capture memory
        self.set_capture_target(CameraDevice.CAPTURE_TARGET_MEMORY_CARD)
        self._camera_object.init()
        self.summary = str(self._camera_object.get_summary())
        self._camera_object.exit()
        self.serial_number = self.camera_summary_get_serial_number(self.summary)

    @staticmethod
    def _get_camera_object_by_addr(camera_addr):
        """
        Get uninitialized Camera object, based on camera address.

        :param camera_addr: Address of the camera from PortInfoList. E.g. "usb:002,041".
        :type camera_addr: str
        :return: gphoto2.Camera
        """
        camera = ThreadsafeCameraObject()

        port_info_list = gp.PortInfoList()
        port_info_list.load()
        idx = port_info_list.lookup_path(camera_addr)
        camera.set_port_info(port_info_list[idx])
        return camera

    @classmethod
    def get_available_cameras(cls):
        """
        Get list of CameraDevice objects representing available cameras

        :return: list of CameraDevice objects
        """
        cameras = list()
        for camera_name, address in CameraDevice._get_available_cameras_raw():
            #log.debug("Found available device '%s(%s)'", camera_name, address)
            try:
                camera = cls.camera_device_cache[address]
            except KeyError:
                camera = None

            # while there is a device on the same address, it seems that it is not the same as before
            if camera is not None and camera.name != camera_name:
                camera = None
                cls.camera_device_cache.pop(address)

            # there is no camera on this address in the cache or something changed. Get a new CameraDevice
            if camera is None:
                try:
                    camera = CameraDevice(camera_name, address)
                except CameraDeviceBusy as err:
                    log.warn("Not using device '%s(%s)' because: %s", camera_name, address, err)
                    continue
                else:
                    cls.camera_device_cache[address] = camera

            cameras.append(camera)

        return cameras

    @staticmethod
    def _get_available_cameras_raw():
        """
        Use gphoto2 autodetect functionality to get list of available cameras

        :return: list of cameras
        :rtype: gphoto2.CameraList of values like "['Canon EOS 1000D', 'usb:002,007']"
        """
        port_info_list = gp.PortInfoList()
        port_info_list.load()
        abilities_list = gp.CameraAbilitiesList()
        abilities_list.load()
        cameras = abilities_list.detect(port_info_list)
        return cameras

    @staticmethod
    def camera_summary_get_serial_number(camera_summary):
        """
        Extracts serial number from provided camera summary text.

        :param camera_summary:
        :return:
        """
        # extract Serial Number
        match = re.search(r'Serial Number: (.*)\n', camera_summary)
        if match:
            serial_number = match.group(1)
            log.debug('Extracted Serial Number: %s', serial_number)
        else:
            log.error('No Serial Number found in the summary')
            serial_number = None
        return serial_number

    def list_files(self, path='/'):
        files = list()
        self._camera_object.init()
        folders = [path]
        for folder in folders:
            # get additional folders in the current folder
            for name, value in self._camera_object.folder_list_folders(folder):
                folders.append(os.path.join(folder, name))
            # get files
            for name, value in self._camera_object.folder_list_files(folder):
                files.append(os.path.join(folder, name))
        self._camera_object.exit()
        return files

    def get_file_info(self, path):
        folder, filename = os.path.split(path)
        self._camera_object.init()
        info = self._camera_object.file_get_info(folder, filename)
        self._camera_object.exit()
        return info

    def set_capture_target(self, target=CAPTURE_TARGET_INTERNAL_RAM):
        self._camera_object.init()
        config = self._camera_object.get_config()
        capture_target_config = config.get_child_by_name('capturetarget')
        capture_target_config.set_value(target)
        self._camera_object.set_config(config)
        self._camera_object.exit()

    def take_picture(self):
        self._camera_object.init()
        file_path = self._camera_object.capture(gp.GP_CAPTURE_IMAGE)
        self._camera_object.exit()
        return os.path.join(file_path.folder, file_path.name)

    def download_picture(self, picture_path, store_path, keep_on_device=False):
        folder, filename = os.path.split(picture_path)
        self._camera_object.init()
        camera_file = self._camera_object.file_get(folder, filename, gp.GP_FILE_TYPE_NORMAL)
        gp.check_result(gp.gp_file_save(camera_file, store_path))
        # delete the file from the device
        if not keep_on_device:
            self._camera_object.file_delete(folder, filename)
        self._camera_object.exit()


if __name__ == '__main__':
    cameras = CameraDevice.get_available_cameras()
    cam1 = cameras[0]
    cam1.set_capture_target(CameraDevice.CAPTURE_TARGET_MEMORY_CARD)
    #log.info("Camera summary %s", cam1.summary)
    log.info("Camera sn %s", cam1.serial_number)
    #log.info("list files %s", cam1.list_files())
    picture = cam1.take_picture()
    log.info("Picture %s", picture)
    store_path = os.path.join(os.getcwd(), os.path.basename(picture))
    cam1.download_picture(picture, store_path)
    log.info("Saved Pic as %s", store_path)
