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
from .errors import RestPoseError, CheckPointExpiredError

class Server(object):
    """Representation of a RestPose server.

    Allows indexing, searching, status management, etc.

    """

    _resource_class = RestPoseResource

    #: Type of waiting to use for calls which modify state.
    #: Possible options are:
    #:
    #:  - `none`: Try pushing tasks onto the queue once, and then return
    #:    immediately, raising a RequestFailed exception if the queue is full.
    #:  - `push`: Push tasks onto the queue, blocking until the task is
    #:    pushed onto the queue.  Errors which occur in processing or indexing
    #:    can be accessed using checkpoints.
    #:  - `process`: Push tasks onto the queue, blocking until the task has
    #:    been processed.  Errors which occur during processing will be
    #:    returned; errors which occur during processing or indexing can be
    #:    accessed using checkpoints.
    #:  - `complete`: Push tasks onto the queue, blocking until the task has
    #:    been fully handled by processing and indexing.  Errors which occur
    #:    during processing or indexing will be returned, and can also be
    #:    accessed using checkpoints.
    wait = "process"

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

    def is_descendant(self, categories):
        """Create a query for field values which are categories which are
        descendants of one of the given categories.

        A document will match if at least one of the stored values for the
        field exactly matches a descendant of the given categories.

        This query type is available only for "cat" field types.

        :param categories: A container holding the categories to search for.
               As a special case, if a string is supplied, this is equivalent
               to supplying a container holding that string.

        :example:

            Search for documents in which the "tag" field is a descendant of
            a value of "cheese"

            >>> query = coll.field.tag.is_descendant('cheese')

            or, equivalently:

            >>> query = coll.field.tag.is_descendant(['cheese'])

        """
        return QueryField(self.fieldname, 'is_descendant', categories,
                          target=self.target)

    def is_or_is_descendant(self, categories):
        """Create a query for field values which are categories which are
        descendants of one of the given categories.

        A document will match if at least one of the stored values for the
        field exactly matches a descendant of the given categories.

        This query type is available only for "cat" field types.

        :param categories: A container holding the categories to search for.
               As a special case, if a string is supplied, this is equivalent
               to supplying a container holding that string.

        :example:

            Search for documents in which the "tag" field has a value of
            "cheese", or has a value which is a descendant of "cheese".

            >>> query = coll.field.tag.is_or_is_descendant('cheese')

            or, equivalently:

            >>> query = coll.field.tag.is_or_is_descendant(['cheese'])

        """
        return QueryField(self.fieldname, 'is_or_is_descendant', categories,
                          target=self.target)

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

    def distscore(self, center, max_range=None):
        """Create a query for geospatial field values based on distance.

        Matches documents in which one of the stored values in the field is
        within the specified range of the center point (in meters on the
        surface of the earth).

        This type is currently available only for "lonlat" field types.

        :param center: The center for the query.  Either a (lon, lat) tuple, or
                       an object with "lon" and "lat" properties; in either
                       case, the longitude and latitude must be stored as
                       numbers.
        :param max_range: The maximum range (in meters) of documents to return;
                       if None, returns documents with no maximum range.  

        :example:

            Search for documents in which the "num" field has a value in the
            range 0 to 10 (including the endpoints).

            >>> query = coll.field.latlon.distscore([0.0, 0.0], 1609.344)

        """
        params = dict(center = center)
        if max_range is not None:
            params['max_range'] = max_range
        return QueryField(self.fieldname, 'distscore', params,
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

        self._realiser = None

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

    def set_realiser(self, realiser):
        """Set the function to get objects associated with results.

        This may be overridden for a particular search by setting a realiser on
        a Searchable.

        """
        self._realiser = realiser
        return self

    def search(self, search):
        """Perform a search.

        :param search: is a search structure to be sent to the server, or a
                       Search or Query object.

        """
        if hasattr(search, '_build_search'):
            body = search._build_search()
            realiser = search._realiser
        else:
            body = search
            realiser = None
        result = self._resource \
            .post(self._basepath + "/search", payload=body) \
            .expect_status(200).json
        return SearchResults(result, realiser or self._realiser)


class Document(object):
    def __init__(self, collection, doc_type, doc_id):
        if collection is None:
            # doc_type should be a DocumentType object.
            self._resource = doc_type._resource
            self._path = doc_type._basepath + '/id/' + doc_id
        else:
            # doc_type should be a string.
            self._resource = collection._resource
            self._path = collection._basepath + '/type/' + doc_type + \
                         '/id/' + doc_id
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

        #: The name of the document type
        self.name = doc_type

        self._basepath = collection._basepath + '/type/' + doc_type
        self._server = collection._server
        self._resource = collection._resource
        self._realiser = collection._realiser

    def add_doc(self, doc, doc_id=None, wait=None):
        """Add a document to the collection.

        :param doc: The document to add (as a dictionary of fields).

        :param doc_id: The ID of the document to add.  If omitted, the ID must
               be present in the document.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

        """
        path = self._basepath
        use_put = True

        if doc_id is None:
            use_put = False
        else:
            path += '/id/%s' % doc_id

        wait = wait or self._server.wait
        if use_put:
            resp = self._resource.put(path, payload=doc, wait=wait)
        else:
            resp = self._resource.post(path, payload=doc, wait=wait)

        return resp.expect_status(202).json

    def delete_doc(self, doc_id, wait=None):
        """Delete a document with this type from the collection.

        """
        path = '%s/id/%s' % (self._basepath, doc_id)
        return self._resource \
            .delete(path, wait=wait or self._server.wait) \
            .expect_status(202).json

    def get_doc(self, doc_id):
        return Document(None, self, doc_id)


class Collection(QueryTarget):
    def __init__(self, server, coll_name):
        super(Collection, self).__init__()

        #: The name of the collection
        self.name = coll_name

        self._basepath = '/coll/' + coll_name
        self._resource = server._resource
        self._server = server

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
        self._resource.put(self._basepath + '/config', payload=value,
                           wait=self._server.wait) \
            .expect_status(202).json

    def add_doc(self, doc, doc_type=None, doc_id=None, wait=None):
        """Add a document to the collection.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

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
            meth = self._resource.put
        else:
            meth = self._resource.post

        wait = wait or self._server.wait
        return meth(path, payload=doc, wait=wait).expect_status(202).json

    def delete_doc(self, doc_type, doc_id, wait=None):
        """Delete a document from the collection.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

        """
        path = '%s/type/%s/id/%s' % (self._basepath, doc_type, doc_id)
        wait = wait or self._server.wait
        return self._resource.delete(path, wait=wait).expect_status(202).json

    def get_doc(self, doc_type, doc_id):
        """Get a document from the collection.

        """
        return Document(self, doc_type, doc_id)

    def checkpoint(self, commit=True, wait=None):
        """Set a checkpoint on the collection.

        This creates a resource on the server which can be queried to detect
        whether indexing has reached the checkpoint yet.  All updates sent
        before the checkpoint will be processed before indexing reaches the
        checkpoint, and no updates sent after the checkpoint will be processed
        before indexing reaches the checkpoint.

        :param commit: If True, the checkpoint will cause a commit to happen.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

        """
        path = self._basepath + "/checkpoint"
        params_dict = {'wait': wait or self._server.wait}
        if commit:
            params_dict['commit'] = '1'
        else:
            params_dict['commit'] = '0'
        return CheckPoint(self, self._resource
                          .post(path, params_dict=params_dict)
                          .expect_status(201)
                          .json)

    def taxonomies(self):
        """Get a list of the taxonomy names.

        """
        path = self._basepath + "/taxonomy"
        return self._resource.get(path).expect_status(200).json

    def taxonomy(self, taxonomy_name):
        """Access a taxonomy, for getting and setting its hierarchy.

        """
        return Taxonomy(self, taxonomy_name)

    def delete(self):
        """Delete the entire collection.

        """
        return self._resource.delete(self._basepath).expect_status(202).json


class CheckPoint(object):
    """A checkpoint, used to check the progress of indexing.

    """
    def __init__(self, collection, response):
        """Create a CheckPoint object.

        :param collection: The collection that the checkpoint is for.

        :param response: The response returned by the server when creating the
               checkpoint.

        """
        self._check_id = response.get('checkid')
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

class Taxonomy(object):
    """A taxonomy; a hierarchy of category relationships.

    A collection may have many taxonomies, each identified by a name.  Each
    taxonomy contains a set of categories, and a tree of parent-child
    relationships (or, to use the correct mathematical terminology, a forest.
    ie, there may be many disjoint trees of parent-child relationships).

    This class allows the relationships in a taxonomy to be obtained and
    modified.

    """
    def __init__(self, collection, taxonomy_name):
        #: The name of the taxonomy
        self.name = taxonomy_name

        self._basepath = collection._basepath + '/taxonomy/' + taxonomy_name
        self._resource = collection._resource
        self._server = collection._server

    def all(self):
        """Get details about the entire set of categories in the taxonomy.

        This returns a dict, keyed by category ID, in which each each value is
        a list of parent category IDs.

        Raises ResourceNotFound if the collection or taxonomy are not found.

        """
        return self._resource.get(self._basepath).expect_status(200).json

    def top(self):
        """Get the top-level category names in the taxonomy.

        This returns a dict representing the categories in the taxonomy which
        have no parents.  The keys are the category IDs, and the values are
        objects with the following properties:

         - child_count: The number of direct child categories of this category.
         - descendant_count: The number of descendants of this category.

        Raises ResourceNotFound if the collection or taxonomy are not found.

        """
        return self._resource.get(self._basepath + '/top') \
            .expect_status(200).json

    def get_category(self, category):
        """Get the details of a category in the taxonomy.

        This returns an object with the following properties:

         - "parents": A list of the category IDs of any direct parents of the
           category.
         - "ancestors": A list of the category IDs of any ancestors of the
           category.
         - "children": A list of the category IDs of any direct children of the
           category.
         - "descendants": A list of the category IDs of any descendants of the
           category.

        Raises ResourceNotFound if the collection, taxonomy or category are not
        found.

        """
        return self._resource.get(self._basepath + '/id/' + category) \
            .expect_status(200).json

    def add_category(self, category, wait=None):
        """Add a category.

        Creates the collection, taxononmy and category if they don't already
        exist.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

        """
        return self._resource \
            .put(self._basepath + '/id/' + category,
                 wait = wait or self._server.wait) \
            .expect_status(202).json

    def remove_category(self, category, wait=None):
        """Remove a category.

        Creates the collection and taxononmy if they don't already exist.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

        """
        return self._resource \
            .delete(self._basepath + '/id/' + category,
                    wait = wait or self._server.wait) \
            .expect_status(202).json

    def add_parent(self, category, parent, wait=None):
        """Add a parent to a category.

        Creates the collection, taxononmy, category and the parent, if
        necessary.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

        """
        return self._resource \
            .put(self._basepath + '/id/' + category + '/parent/' + parent,
                 wait = wait or self._server.wait) \
            .expect_status(202).json

    def remove_parent(self, category, parent, wait=None):
        """Remove a parent from a category.

        Creates the collection and taxononmy if they don't already exist.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

        """
        return self._resource \
            .delete(self._basepath + '/id/' + category + '/parent/' + parent,
                    wait = wait or self._server.wait) \
            .expect_status(202).json

    def remove(self, wait=None):
        """Remove this entire taxonomy.

        :param wait: The type of waiting to use.  Defaults to that specified by
               server.wait.

        """
        return self._resource \
            .delete(self._basepath, wait = wait or self._server.wait) \
            .expect_status(202).json
