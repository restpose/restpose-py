# -*- coding: utf-8 -
#
# This file is part of the restpose python module, released under the MIT
# license.  See the COPYING file for more information.

"""
Resources for RestPose.

This module provides a convenient interface to the resources exposed via HTTP
by the RestPose server.

"""

from .version import __version__
from .errors import RestPoseError
import restkit
import json
import six
import sys

class RestPoseResponse(restkit.Response):
    """A response from the RestPose server.

    In addition to the properties exposed by :mod:`restkit:restkit.Response`, this
    exposes a `json` property, to decode JSON responses automatically.

    """

    @property
    def json(self):
        """Get the response body as JSON.

        :returns: The response body as a python object, decoded from JSON, if
                  the response Content-Type was application/json.

        :raises: an exception if the Content-Type is not application/json, or
                 the body is not valid JSON.

        :raises: :exc:`RestPoseError` if the status code returned is not one of the supplied status codes.

        """
        ctype = self.headers.get('Content-Type')
        if ctype == 'application/json':
            return json.loads(self.body_string())
        raise RestPoseError("Unexpected return content type: %s" % ctype)

    def expect_status(self, *expected):
        """Check that the status code is one of a set of expected codes.

        :param expected: The expected status codes.

        :raises: :exc:`RestPoseError` if the status code returned is not one of
                 the supplied status codes.

        """
        if self.status_int not in expected:
            raise RestPoseError("Unexpected return status: %d" %
                                self.status_int)
        return self


class RestPoseResource(restkit.Resource):
    """A resource providing access to a RestPose server.

    This may be subclassed and provided to :class:`restpose.Server`, to
    allow requests to be monitored or modified.  For example, a logging
    subclass could be used to record requests and their responses.

    """

    #: The user agent to send when making requests.
    user_agent = 'restpose_python/%s' % __version__

    def __init__(self, uri, **client_opts):
        """Initialise the resource.

        :param uri: The full URI for the resource.

        :param client_opts: Any options to be passed to :class:`restkit.Resource`.

        """
        client_opts['response_class'] = RestPoseResponse
        super(RestPoseResource, self).__init__(uri=uri, **client_opts)

    def request(self, method, path=None, payload=None, headers=None, **params):
        """Perform a request.

        :param method: the HTTP method to use, as a string.
        :param path: The path to request.
        :param payload: A payload to send as the request body; may be a
               file-like object, or a string, or a structure to send encoded as
               a JSON object.
        :param headers: A dictionary of headers.  If not already set, Accept
               and User-Agent headers will be added to this, and if there is a
               JSON payload, the Content-Type will be set to application/json.
        :param params: A dictionary of parameters to add to the request URI.

        """

        headers = headers or {}
        headers.setdefault('Accept', 'application/json')
        headers.setdefault('User-Agent', self.user_agent)

        if payload is not None:
            if not hasattr(payload, 'read') and \
               not isinstance(payload, six.string_types):
                payload = json.dumps(payload).encode('utf-8')
                headers.setdefault('Content-Type', 'application/json')

        try:
            resp = super(RestPoseResource, self).request(
                method, path=path,
                payload=payload, headers=headers,
                **params)
        except restkit.ResourceError:
            e = sys.exc_info()[1] # Python 2/3 compatibility
            # Unpack any errors which are in JSON format.
            msg = getattr(e, 'msg', '')
            msgobj = None
            if e.response and msg:
                ctype = e.response.headers.get('Content-Type')
                if ctype == 'application/json':
                    msgobj = json.loads(msg)
            if msgobj is not None:
                e.msg = msgobj.get('err', '')
            e.msgobj = msgobj
            raise

        return resp
