# -*- coding: utf-8 -
#
# This file is part of the restpose python module, released under the MIT
# license.  See the COPYING file for more information.
"""Version information.

"""
import six
#: The development release suffix.  Will be an empty string for releases.
dev_release = ""

#: The version of this restpose client, as a tuple of numbers.
#: This does not include information about whether this is a development
#: release.
version_info = (0, 7, 7)

#: The version of this restpose client, as a string.
#: This will have a development release suffix for development releases.
__version__ =  ".".join(map(six.text_type, version_info)) + dev_release
