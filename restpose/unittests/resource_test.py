# -*- coding: utf-8 -
#
# This file is part of the restpose python module, released under the MIT
# license.  See the COPYING file for more information.

from .helpers import RestPoseTestCase
from ..resource import RestPoseResource
from ..errors import RestPoseError
from restkit import ResourceError
import sys

class ResourceTest(RestPoseTestCase):
    maxDiff = 10000

    def setUp(self):
        self.r = RestPoseResource('http://127.0.0.1:7777/')

    def test_bad_response(self):
        """Check error handling when response isn't in expected format.

        """
        resp = self.r.get('/')

        # Content returned by / isn't JSON
        self.assertRaises(RestPoseError, getattr, resp, 'json')

        self.assertEqual(resp.status_int, 200)
        self.assertRaises(RestPoseError, resp.expect_status, 400)
