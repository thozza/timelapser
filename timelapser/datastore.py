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
import abc
import shutil

import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import AuthError, ApiError

from timelapser.log import log


class DataSaveError(Exception):
    pass


class BaseDataStore:

    @abc.abstractmethod
    def store_file(self, file, remove_original=True):
        pass


class FilesystemDataStore(BaseDataStore):

    def __init__(self, store_path):
        self._store_path = store_path
        if not os.path.isdir(self._store_path):
            os.makedirs(self._store_path)

    def __str__(self):
        return "<FilesystemDataStore(id={} store_path={})>".format(
                id(self),
                self._store_path
                )

    def store_file(self, file, remove_original=True):
        filename = os.path.basename(file)
        move_path = os.path.join(self._store_path, filename)

        if remove_original:
            log.debug("Removing the original file %s", file)
            shutil.move(file, move_path)
        else:
            shutil.copyfile(file, move_path)


class DropboxDataStore(BaseDataStore):
    """
    Class for saving files directly into Dropbox
    """

    def __init__(self, token, store_path):
        self._dropbox = dropbox.Dropbox(token)
        self._store_path = store_path

        try:
            user_account = self._dropbox.users_get_current_account()
        except AuthError:
            raise RuntimeError("Invalid Dropbox access token. Try re-generating access token from the app console on \
            the web")
        else:
            log.debug("Successfully logged into Dropbox as user '%s'", user_account.name)
        # TODO: check that the directory in store_path exists and if not, create it!

    def __str__(self):
        return "<DropboxDataStore(id={} store_path={})>".format(
                id(self),
                self._store_path
                )

    def store_file(self, file, remove_original=True):
        filename = os.path.basename(file)
        upload_path = os.path.join(self._store_path, filename)
        log.debug("Uploading file '%s' into Dropbox as '%s'", filename, upload_path)
        with open(file, "rb") as f:
            try:
                self._dropbox.files_upload(f.read(), upload_path, mode=WriteMode('overwrite'))
            except ApiError as err:
                if err.error.is_path() and err.error.get_path().reason.is_insufficient_space():
                    log.error("Cannot back up; insufficient space.")
                elif err.user_message_text:
                    log.error(err.user_message_text)
                else:
                    log.error(err)
                raise DataSaveError("Failed to upload file to Dropbox.")
            except Exception as err:
                log.error(err)
                raise DataSaveError("Failed to upload file to Dropbox due to error: {}".format(err))

        if remove_original:
            log.debug("Removing the original file %s", file)
            os.remove(file)
