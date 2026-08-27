"""Windows compatibility: mock the Unix-only `pwd` module.

Some dependencies (e.g. crawl4ai's file utilities) import `pwd`, which does
not exist on Windows. Importing this module before them installs a minimal
stand-in. This is the surviving piece of the deleted backend/patches package.
"""
import platform
import sys
import types


class struct_passwd:
    def __init__(self, pw_name="", pw_passwd="", pw_uid=0, pw_gid=0, pw_gecos="", pw_dir="", pw_shell=""):
        self.pw_name = pw_name
        self.pw_passwd = pw_passwd
        self.pw_uid = pw_uid
        self.pw_gid = pw_gid
        self.pw_gecos = pw_gecos
        self.pw_dir = pw_dir
        self.pw_shell = pw_shell


def _getpwuid(uid):
    return struct_passwd(pw_name="user", pw_uid=uid)


def _getpwnam(name):
    return struct_passwd(pw_name=name)


def _getpwall():
    return [struct_passwd(pw_name="user")]


if platform.system() == "Windows" and "pwd" not in sys.modules:
    _pwd = types.ModuleType("pwd")
    _pwd.struct_passwd = struct_passwd
    _pwd.getpwuid = _getpwuid
    _pwd.getpwnam = _getpwnam
    _pwd.getpwall = _getpwall
    sys.modules["pwd"] = _pwd
