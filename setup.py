from DistUtilsExtra.auto import setup
from distutils.command.install import install
import os

PACKAGE="python-utility-modules"
VERSION="1.0"

# In case we need hooks
class post_install(install):
    def run(self):
        install.run(self)

setup(
    name              = PACKAGE,
    author            = "Gary Oliver",
    author_email      = "go@robosity.com",
    url               = "http://robosity.com",
    version           = VERSION,
    packages          = [ "python-utility-modules" ],
    license           = "Copyright 2018, Robosity Codeworks" ],
    description       = "Miscellaneous Utilities",
    long_description  = open("README.md").read(),
    cmdclass          = { 'install': post_install },
)
