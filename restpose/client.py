# -*- coding: utf-8 -
#
# This file is part of the restpose python module, released under the MIT
# license.  See the COPYING file for more information.

"""
The RestPose client mirrors the resources provided by the RestPose server as
Python objects.

.. testsetup::

    from restpose import Server
    coll = Server().collection('test_coll')

"""

import six
from .resource import RestPoseResource
from .query import Query, QueryAll, QueryNone, QueryField, QueryMeta, \
                   SearchResults
import query
from .errors import RestPoseError, CheckPointExpiredError

class Server(object):
    """Representation of a RestPose server.

    Allows indexing, searching, status management, etc.

    """

    _resource_class = RestPoseResource

    def __init__(self, uri='http://127.0.0.1:7777',
                 resource_class=None,
                 resource_instance=None,
                 **client_opts):
        """
        :param uri: Full URI to the top path of the server.

        :param resource_class: If specified, defines a resource class to use
               instead of the default class.  This should usually be a subclass
               of :class:`RestPoseResource`.

        :param resource_instance: If specified, defines a resource instance to
               use instead of making one with the default class (or the class
               specified by `resource_class`.

        :param client_opts: Parameters to use to update the existing
               client_opts in the resource (if `resource_instance` is
               specified), or to use when creating the resource (if
               `resource_class` is specified).

        """
        self.uri = uri = uri.rstrip('/')

        if resource_class is not None:
            self._resource_class = resource_class

        if resource_instance:
            self._resource = resource_instance.clone()
            self._resource.initial['uri'] = uri
            self._resource.client_opts.update(client_opts)
        else:
            self._resource = self._resource_class(uri, **client_opts)

    @property
    def status(self):
        """Get server status.

        Returns a dictionary holding the status as returned from the server.
        See the server documentation for details.

        """
        return self._resource.get('/status').expect_status(200).json

    @property
    def collections(self):
        """Get a list of existing collections.

        Returns a list of collection names (as strings).

        """
        return list(self._resource.get('/coll').expect_status(200).json.keys())

    def collection(self, coll_name):
        """Access to a collection.

        :param coll_name: The name of the collection to access.

        :returns: a Collection object which can be used to search and modify the
                  contents of the Collection.

        .. note:: No request is performed directly by this method; a Collection
                  object is simply created which will make requests when
                  needed.  For this reason, no error will be reported at this
                  stage even if the collection does not exist, or if a
                  collection name containing invalid characters is used.

        """
        return Collection(self, coll_name)


class FieldQueryFactory(object):
    """Object for creating searches on a field.

    """

    def __init__(self, target=None):
        """
        :param target: The target to pass to the Query objects created.

        """
        #: The target that will be used when creating Query objects.  Defaults
        #: to None.
        self.target = target

    def __call__(self, fieldname):
        """Create a FieldQuerySource for the given fieldname.

        This is mainly intended for use for fieldnames which are stored in a
        parameter, or which are reserved or invalid Python identifiers.

        """
        return FieldQuerySource(fieldname, self.target)

    def __getattr__(self, fieldname):
        """Get a FieldQuerySource for the given fieldname.

        The FieldQuerySource has various operators used to build queries.

        """
        return FieldQuerySource(fieldname, self.target)


class FieldQuerySource(object):
    """An object which generates queries for a specific field.

    """
    def __init__(self, fieldname, target=None):
        """
        :param fieldname: The name of the field to generate queries for.  If
               set to None, will generate queries across all fields.
        :param target: The target to generate queries pointing to.

        """
        self.fieldname = fieldname
        self.target = target

    def is_in(self, values):
        """Create a query for fields which exactly match the given values.

        A document will match if at least one of the stored values for the
        field exactly matches at least one of the given values.

        This query type is currently available only for "exact", "id" and "cat"
        field types.

        :param value: A container holding the values to search for.  As a
               special case, if a string is supplied, this is equivalent to
               supplying a container holding that string.

        :example:

            Search for documents in which the "tag" field has a value of
            "edam", "cheddar" or "leicester".

            >>> query = coll.field.tag.is_in(['edam', 'cheddar', 'leicester'])

            Search for documents in which the "tag" field has a value of
            "edam".

            >>> query = coll.field.tag.is_in('edam')

        """
        return QueryField(self.fieldname, 'is', values, target=self.target)

    # FIXME - add "is_descendant" and "is_or_is_descendant"

    def __eq__(self, value):
        """Create a query for fields which exactly match the given value.

        Matches documents in which the supplied value exactly matches the
        stored value.

        This query type is currently available only for "exact", "id" and "cat"
        field types.

        This query type may be constructed using the == operator, or the
        ``equals`` method.

        :param value: The value to search for.

        :example:

            Search for documents in which the "tag" field has a value of
            "edam".

            >>> query = coll.field.tag.equals('edam')

            Or, equivalently (but less conveniently for chained calls)

            >>> query = (coll.field.tag == 'edam')

        """
        return QueryField(self.fieldname, 'is', (value,), target=self.target)
    equals = __eq__

    def range(self, begin, end):
        """Create a query for field values in a given range.

        Matches documents in which one of the stored values in the field are in
        the specified range, including both the begin and end values.

        This type is currently available only for "double", "date" and
        "timestamp" field types.

        :param begin: The start of the range.
        :param end: The end of the range.

        :example:

            Search for documents in which the "num" field has a value in the
            range 0 to 10 (including the endpoints).

            >>> query = coll.field.num.range(0, 10)

        """
        return QueryField(self.fieldname, 'range', (begin, end),
                          target=self.target)

    def text(self, text, op="phrase", window=None):
        """Create a query for a piece of text in the field.

        This is a simple search for a matching sequences of words (subject to
        whatever processing has been performed on the field to conflate variant
        forms of words, such as stemming or word splitting for CJK text).

        :param text: The text to search for.  If empty, this query will
               match no results.
        :param op: The operator to use when searching.  One of "or", "and",
               "phrase" (ordered proximity), "near" (unordered proximity).
               Default="phrase".
        :param window: Only relevant if op is "phrase" or "near". Window size
               in words within which the words in the text need to occur for a
               document to match; None=length of text. Integer or None.
               Default=None

        :example:

            Search for documents in which the "text" field contains text
            matching the phrase "Hello world".

            >>> query = coll.field.text.text("Hello world")

        """
        value = dict(text=text)
        if op is not None:
            value['op'] = op
        if window is not None:
            value['window'] = window
        return QueryField(self.fieldname, 'text', value, target=self.target)

    def parse(self, text, op="and"):
        """Parse a structured query, searching the field.

        Unlike text, this allows various operators to be used in the query; for
        example, parentheses may be used, and operators such as "AND" may be
        used 

        .. todo:: Document the operators permitted.

        Beware that the parser is unable to make sense of some query strings
        (eg, those with mismatched parentheses).  If such a query string is
        used, an error will be returned by the server when the search is
        performed.

        :param fieldname: The field to search within.
        :param text: Text to search for.  If empty, this query will match no
               results.
        :param op: The default operator to use when searching.  One of "or",
               "and".  Default="and".

        :example:

            Search for documents in which the "text" field contains both
            "Hello" and "world", but not "big".

            >>> query = coll.field.text.text("Hello world -big")

        """
        value = dict(text=text)
        if op is not None:
            value['op'] = op
        return QueryField(self.fieldname, 'parse', value, target=self.target)

    def exists(self):
        """Search for documents in which the field exists.

        This type may be used to search across all fields.

        :example:

            Search for documents in which the "text" field exists.

            >>> query = coll.field.text.exists()

            Search for documents in which any field exists.

            >>> query = coll.any_field.exists()

        """
        return QueryMeta('exists', (self.fieldname,), target=self.target)

    def nonempty(self):
        """Search for documents in which the field has a non-empty value.

        This type may be used to search across all fields.

        :example:

            Search for documents in which the "text" field has a non-empty
            value.

            >>> query = coll.field.text.nonempty()

            Search for documents in which any field has a non-empty value.

            >>> query = coll.any_field.nonempty()

        """
        return QueryMeta('nonempty', (self.fieldname,), target=self.target)

    def empty(self):
        """Search for documents in which the field has an empty value.

        This type may be used to search across all fields.

        :example:

            Search for documents in which the "text" field has an empty
            value.

            >>> query = coll.field.text.empty()

            Search for documents in which any field has an empty value.

            >>> query = coll.any_field.empty()

        """
        return QueryMeta('empty', (self.fieldname,), target=self.target)

    def has_error(self):
        """Search for documents in which the field produced errors when
        parsing.

        This type may be used to search across all fields.

        :example:

            Search for documents in which the "text" field had an error when
            parsing.

            >>> query = coll.field.text.has_error()

            Search for documents in which any field had an error when parsing.

            >>> query = coll.any_field.has_error()

        """
        return QueryMeta('error', (self.fieldname,), target=self.target)


Field = FieldQueryFactory()
AnyField = FieldQuerySource(fieldname=None)

class QueryTarget(object):
    """An object which can be used to make and run queries.

    """
    def __init__(self):
        #: Factory for field-specific queries.
        self.field = FieldQueryFactory(target=self)

        #: Pseudo field for making queries across all fields.
        self.any_field = FieldQuerySource(fieldname=None, target=self)

    def all(self):
        """Create a query which matches all documents."""
        return QueryAll(target=self)

    def none(self):
        """Create a query which matches no documents."""
        return QueryNone(target=self)

    def find(self, q):
        """Apply a Query to this QueryTarget.

        :param q: A Query object which will have the target applied to it.

        """
        return q.set_target(self)

    def search(self, search):
        """Perform a search.

        :param search: is a search structure to be sent to the server, or a
                       Search or Query object.

        """
        if hasattr(search, '_build_search'):
            body = search._build_search()
        else:
            body = search
        result = self._resource.post(self._basepath + "/search",
                                     payload=body).json
        return SearchResults(result)


class Document(object):
    def __init__(self, collection, doc_type, doc_id):
        if collection is None:
            # doc_type should be a DocumentType object.
            self._resource = doc_type._resource
            self._path = doc_type._basepath + '/id/' + doc_id
        else:
            # doc_type should be a string.
            self._resource = collection._resource
            self._path = collection._basepath + '/type/' + doc_type + '/id/' + doc_id
        self._data = None
        self._terms = None
        self._values = None
        self._raw = None

    def _fetch(self):
        self._raw = self._resource.get(self._path).expect_status(200).json
        self._data = self._raw.get('data', {})
        self._terms = self._raw.get('terms', {})
        self._values = self._raw.get('values', {})

    @property
    def data(self):
        if self._raw is None:
            self._fetch()
        return self._data

    @property
    def terms(self):
        if self._raw is None:
            self._fetch()
        return self._terms

    @property
    def values(self):
        if self._raw is None:
            self._fetch()
        return self._values


class DocumentType(QueryTarget):
    def __init__(self, collection, doc_type):
        super(DocumentType, self).__init__()
        self._basepath = collection._basepath + '/type/' + doc_type
        self._resource = collection._resource

    def add_doc(self, doc, doc_id=None):
        """Add a document to the collection.

        """
        path = self._basepath
        use_put = True

        if doc_id is None:
            use_put = False
        else:
            path += '/id/%s' % doc_id

        if use_put:
            resp = self._resource.put(path, payload=doc)
        else:
            resp = self._resource.post(path, payload=doc)

        return resp.expect_status(202)

    def delete_doc(self, doc_id):
        """Delete a document with this type from the collection.

        """
        path = '%s/id/%s' % (self._basepath, doc_id)
        return self._resource.delete(path).expect_status(202)

    def get_doc(self, doc_id):
        return Document(None, self, doc_id)


class Collection(QueryTarget):
    def __init__(self, server, coll_name):
        super(Collection, self).__init__()
        self._basepath = '/coll/' + coll_name
        self._resource = server._resource

    def doc_type(self, doc_type):
        return DocumentType(self, doc_type)

    @property
    def status(self):
        """The status of the collection.

        """
        return self._resource.get(self._basepath).expect_status(200).json

    @property
    def config(self):
        """The configuration of the collection.

        """
        return self._resource.get(self._basepath + '/config') \
              .expect_status(200).json

    @config.setter
    def config(self, value):
        self._resource.put(self._basepath + '/config', payload=value) \
            .expect_status(202)

    def add_doc(self, doc, doc_type=None, doc_id=None):
        """Add a document to the collection.

        """
        path = self._basepath
        use_put = True

        if doc_type is None:
            use_put = False
        else:
            path += '/type/%s' % doc_type

        if doc_id is None:
            use_put = False
        else:
            path += '/id/%s' % doc_id

        if use_put:
            resp = self._resource.put(path, payload=doc)
        else:
            resp = self._resource.post(path, payload=doc)

        return resp.expect_status(202)

    def delete_doc(self, doc_type, doc_id):
        """Delete a document from the collection.

        """
        path = '%s/type/%s/id/%s' % (self._basepath, doc_type, doc_id)
        return self._resource.delete(path).expect_status(202)

    def get_doc(self, doc_type, doc_id):
        """Get a document from the collection.

        """
        return Document(self, doc_type, doc_id)

    def checkpoint(self, commit=True):
        """Set a checkpoint on the collection.

        This creates a resource on the server which can be queried to detect
        whether indexing has reached the checkpoint yet.  All updates sent
        before the checkpoint will be processed before indexing reaches the
        checkpoint, and no updates sent after the checkpoint will be processed
        before indexing reaches the checkpoint.

        """
        path = self._basepath + "/checkpoint"
        params_dict = {}
        if commit:
            params_dict['commit'] = '1'
        else:
            params_dict['commit'] = '0'
        return CheckPoint(self, self._resource
                          .post(path, params_dict=params_dict)
                          .expect_status(201)
                          .json.get('checkid'))

    def delete(self):
        """Delete the entire collection.

        """
        return self._resource.delete(self._basepath).expect_status(202)


class CheckPoint(object):
    """A checkpoint, used to check the progress of indexing.

    """
    def __init__(self, collection, check_id):
        self._check_id = check_id
        self._basepath = collection._basepath + '/checkpoint/' + self._check_id
        self._resource = collection._resource

        # The raw representation of the checkpoint, as returned from the
        # request, or None if the checkpoint hasn't been reached or expired, or
        # 'expired' if the checkpoint has expired.
        self._raw = None

    @property
    def check_id(self):
        """The ID of the checkpoint.

        This is used to identify the checkpoint on the server.

        """
        return self._check_id

    def _refresh(self):
        """Contact the server, and get the status of the checkpoint.

        If the checkpoint referred to by this Checkpoint instance has
        previously been found to have been reached or expired, this doesn't
        contact the server, since the checkpoint should no longer change at
        this point.

        """
        if self._raw is None:
            resp = self._resource.get(self._basepath).expect_status(200).json
            if resp is None:
                self._raw = 'expired'
            elif resp.get('reached', False):
                self._raw = resp

        if self._raw == 'expired':
            raise CheckPointExpiredError("Checkpoint %s expired" %
                                         self.check_id)

    @property
    def reached(self):
        """Return true if the checkpoint has been reached.

        May contact the server to check the current state.

        Raises CheckPointExpiredError if the checkpoint expired before the
        state was checked.

        """
        self._refresh()
        return self._raw is not None and self._raw != 'expired'

    @property
    def errors(self):
        """Return the list of errors associated with the CheckPoint.

        Note that if there are many errors, only the first few will be
        returned.

        Returns None if the checkpoint hasn't been reached yet.

        Raises CheckPointExpiredError if the checkpoint expired before the
        state was checked.

        """
        self._refresh()
        return self._raw.get('errors', [])

    @property
    def total_errors(self):
        """Return the total count of errors associated with the CheckPoint.

        This may be larger than len(self.errors), if there were more errors
        than the CheckPoint is able to hold.

        Returns None if the checkpoint hasn't been reached yet.

        Raises CheckPointExpiredError if the checkpoint expired before the
        state was checked.

        """
        self._refresh()
        return self._raw.get('total_errors', 0)

    def wait(self):
        """Wait for the checkpoint to be reached.

        This will contact the server, and wait until the checkpoint has been
        reached.

        If the checkpoint expires (before or during the call), a
        CheckPointExpiredError will be raised.  Otherwise, this will return the
        checkpoint, so that further methods can be chained on it.

        """
        while True:
            self._refresh()
            if self._raw is not None:
                return self
            # FIXME - sleep a bit.  Currently the server doesn't long-poll for
            # the checkpoint, so we need to sleep to avoid using lots of CPU.
            import time
            time.sleep(1)
