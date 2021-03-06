#!/usr/bin/env python
#
# ELBE - Debian Based Embedded Rootfilesystem Builder
# Copyright (C) 2014  Linutronix GmbH
#
# This file is part of ELBE.
#
# ELBE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ELBE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ELBE.  If not, see <http://www.gnu.org/licenses/>.

import binascii
import os
import tarfile
import fnmatch

from tempfile import NamedTemporaryFile

from elbepack.shellhelper import system
from elbepack.version import elbe_version

from faults import soap_faults

from elbepack.elbexml import ValidationMode
from datatypes import SoapProject, SoapFile
from authentication import authenticated_admin, authenticated_uid

from spyne.service import ServiceBase
from spyne.decorator import rpc
from spyne.model.primitive import String, Boolean, Integer
from spyne.model.complex import Array

class ESoap (ServiceBase):

    __name__ = 'soap'

    @rpc (_returns=String )
    @soap_faults
    def get_version(self):
        return elbe_version

    @rpc (String, String, _returns=Boolean )
    @soap_faults
    def login(self, user, passwd):
        s = self.transport.req_env['beaker.session']
        s['userid'] = self.app.pm.db.validate_login(user, passwd)
        s.save()
        return True


    @rpc (_returns=Array(String))
    @soap_faults
    @authenticated_admin
    def list_users (ctx):
        return [u.name for u in ctx.app.pm.db.list_users ()]

    @rpc (_returns=Array(SoapProject))
    @soap_faults
    @authenticated_admin
    def list_projects (ctx):
        return ctx.app.pm.db.list_projects()

    @rpc (String, String, _returns=Array(SoapFile))
    @authenticated_uid
    @soap_faults
    def get_files (self, uid, builddir, _returns=Array(SoapFile)):
        files = self.app.pm.db.get_project_files (builddir)
        return [SoapFile(f) for f in files]

    @rpc (String, String, String, Integer, _returns=Integer)
    @authenticated_uid
    @soap_faults
    def upload_file (self, uid, builddir, fname, blob, part):
        fn = os.path.join (builddir, fname)
        if (part == 0):
            if self.app.pm.db.is_busy (builddir):
                return -1
            self.app.pm.db.set_busy (builddir,
                [ "empty_project", "needs_build", "has_changes",
                  "build_done", "build_failed" ] )
            #truncate file
            with open (fn, 'w') as fp:
                fp.write ('')

        if part == -1:
            with open (fn, 'a') as fp:
                fp.flush ()
            self.app.pm.db.reset_busy (builddir, "has_changes")
            if (fname == "source.xml"):
                # ensure that the project cache is reloaded
                self.app.pm.close_current_project (uid)
                self.app.pm.open_project (uid, builddir, url_validation=ValidationMode.NO_CHECK)
                self.app.pm.set_current_project_xml (uid, fn)
            return -2

        with open (fn, 'a') as fp:
            fp.write (binascii.a2b_base64 (blob))

        return part+1

    @rpc (String, String, Integer, _returns=String)
    @authenticated_uid
    @soap_faults
    def get_file (self, uid, builddir, filename, part):
        size = 1024 * 1024 * 5
        pos = size * part
        file_name = builddir + "/" + filename
        file_stat = os.stat (file_name)

        if (pos >= file_stat.st_size):
            return "EndOfFile"

        with file (file_name) as fp:
            if not fp:
                return "FileNotFound"
            try:
                fp.seek (pos)
                data = fp.read (size)
                return binascii.b2a_base64 (data)
            except:
                return "EndOfFile"

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def build_chroot_tarball (self, uid, builddir):
        self.app.pm.open_project (uid, builddir)
        self.app.pm.build_chroot_tarball (uid)

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def build_sysroot (self, uid, builddir):
        self.app.pm.open_project (uid, builddir)
        self.app.pm.build_sysroot (uid)

    @rpc (String, Boolean, Boolean, Boolean)
    @authenticated_uid
    @soap_faults
    def build (self, uid, builddir, build_bin, build_src, skip_pbuilder):
        self.app.pm.open_project (uid, builddir)
        self.app.pm.build_current_project (uid, build_bin, build_src,
                skip_pbuilder)

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def build_pbuilder (self, uid, builddir):
        self.app.pm.open_project (uid, builddir)
        self.app.pm.build_pbuilder (uid)

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def start_cdrom (self, uid, builddir):
        self.app.pm.open_project (uid, builddir, url_validation=ValidationMode.NO_CHECK)

        cdrom_fname = os.path.join (builddir, "uploaded_cdrom.iso")

        # Now write empty File
        fp = open (cdrom_fname, "w")
        fp.close()

    @rpc (String, String)
    @authenticated_uid
    @soap_faults
    def append_cdrom (self, uid, builddir, data):
        self.app.pm.open_project (uid, builddir, url_validation=ValidationMode.NO_CHECK)

        cdrom_fname = os.path.join (builddir, "uploaded_cdrom.iso")

        # Now append data to cdrom_file
        fp = open (cdrom_fname, "a")
        fp.write (binascii.a2b_base64 (data))
        fp.close()

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def finish_cdrom (self, uid, builddir):
        self.app.pm.open_project (uid, builddir, url_validation=ValidationMode.NO_CHECK)
        self.app.pm.set_current_project_upload_cdrom (uid)

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def start_pdebuild (self, uid, builddir):
        self.app.pm.open_project (uid, builddir)

        pdebuild_fname = os.path.join (builddir, "current_pdebuild.tar.gz")

        # Now write empty File
        fp = open (pdebuild_fname, "w")
        fp.close()

    @rpc (String, String)
    @authenticated_uid
    @soap_faults
    def append_pdebuild (self, uid, builddir, data):
        self.app.pm.open_project (uid, builddir)

        pdebuild_fname = os.path.join (builddir, "current_pdebuild.tar.gz")

        # Now write empty File
        fp = open (pdebuild_fname, "a")
        fp.write (binascii.a2b_base64 (data))
        fp.close()

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def finish_pdebuild (self, uid, builddir):
        self.app.pm.open_project (uid, builddir)
        self.app.pm.build_current_pdebuild (uid)

    @rpc (String, String)
    @authenticated_uid
    @soap_faults
    def start_upload_orig (self, uid, builddir, fname):
        self.app.pm.open_project (uid, builddir)

        orig_fname = os.path.join (builddir, fname)

        # Now write empty File
        fp = open (orig_fname, "w")
        fp.close()

        self.app.pm.set_orig_fname(uid, fname)


    @rpc (String, String)
    @authenticated_uid
    @soap_faults
    def append_upload_orig (self, uid, builddir, data):
        self.app.pm.open_project (uid, builddir)

        orig_fname = os.path.join (builddir, self.app.pm.get_orig_fname(uid))

        # Now append to File
        fp = open (orig_fname, "a")
        fp.write (binascii.a2b_base64 (data))
        fp.close()

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def finish_upload_orig (self, uid, builddir):
        # If we support more than one orig, we need to put the orig_files into some
        # list here.
        # We still need the notion of a "current" orig during file upload.
        pass

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def reset_project (self, uid, builddir):
        self.app.pm.db.reset_project (builddir, True)

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def del_project (self, uid, builddir):
        self.app.pm.del_project (uid, builddir)

    @rpc(String, String, _returns=String)
    @authenticated_uid
    @soap_faults
    def create_project (self, uid, xml, url_validation):
        with NamedTemporaryFile() as fp:
            fp.write (binascii.a2b_base64 (xml))
            fp.flush ()
            prjid = self.app.pm.create_project (uid, fp.name, url_validation=url_validation)

        return prjid

    @rpc(String, _returns=String)
    @authenticated_uid
    @soap_faults
    def new_project (self, uid, url_validation):
        return self.app.pm.new_project (uid)

    @rpc (String, Integer, _returns=String)
    @authenticated_uid
    @soap_faults
    def get_project_busy (self, uid, builddir, part):
        self.app.pm.open_project (uid, builddir)
        ret,log = self.app.pm.current_project_is_busy (uid, part)
        # return bool value to be compatible with elbe v1.0
        if (part == None) and (log == "") and (not ret):
            return ret
        if not ret:
            return 'FINISH'
        return log

    @rpc ()
    @authenticated_uid
    @soap_faults
    def shutdown_initvm (self, uid):
        system ("systemctl --no-block poweroff")

    @rpc (String)
    @authenticated_uid
    @soap_faults
    def rm_log (self, uid, builddir):
        self.app.pm.open_project (uid, builddir)
        self.app.pm.rm_log (uid, builddir)

    @rpc(String, _returns=String)
    @authenticated_uid
    @soap_faults
    def list_packages (self, uid, builddir):
        s = ''
        for root, dirnames, filenames in os.walk(os.path.join(builddir, "repo/pool/main")):
            for filename in fnmatch.filter(filenames, '*.deb'):
                s += filename +'\n'
        return s

    @rpc (String, String)
    @authenticated_uid
    @soap_faults
    def tar_prjrepo (self, uid, builddir, filename):
        self.app.pm.open_project (uid, builddir)
        with tarfile.open(os.path.join(builddir, filename), "w:gz") as tar:
            tar.add(os.path.join(builddir, "repo"), arcname=os.path.basename(os.path.join(builddir, "repo")))

    @rpc (String, String)
    @authenticated_uid
    @soap_faults
    def include_package (self, uid, builddir, filename):
        self.app.pm.open_project (uid, builddir)
        self.app.pm.add_deb_package(uid, filename)
