"""
Mock implementation of the Unix-specific pwd module for Windows compatibility.
This provides minimal functionality to prevent import errors when using libraries 
that expect pwd to be available.
"""

# Define a minimal struct_passwd class that mimics the Unix version
class struct_passwd:
    def __init__(self, pw_name="", pw_passwd="", pw_uid=0, pw_gid=0, 
                 pw_gecos="", pw_dir="", pw_shell=""):
        self.pw_name = pw_name
        self.pw_passwd = pw_passwd
        self.pw_uid = pw_uid
        self.pw_gid = pw_gid
        self.pw_gecos = pw_gecos
        self.pw_dir = pw_dir
        self.pw_shell = pw_shell

# Mock functions that the pwd module provides
def getpwuid(uid):
    """Mock implementation of getpwuid"""
    return struct_passwd(pw_name="user", pw_uid=uid)

def getpwnam(name):
    """Mock implementation of getpwnam"""
    return struct_passwd(pw_name=name)

def getpwall():
    """Mock implementation of getpwall"""
    return [struct_passwd()]
