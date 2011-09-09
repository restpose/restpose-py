Overview
========

So, let's suppose you have some documents that you want to search.  The first
thing to do is to get the RestPose server installed and running; see the
RestPose documentation on :ref:`restpose:installation` for details of this.

Then, you can install the RestPose python client (we suggest in a virtualenv),
using::

    $ pip install restpose

Indexing some documents is as simple as:

.. testsetup::

    import restpose 
    from restpose import Field, And, Or, Xor, AndNot, Filter, AndMaybe, \
                         MultWeight
    server = restpose.Server('http://localhost:7777')
    coll = server.collection("test_coll")
    coll.delete()
    coll.checkpoint().wait()

.. testcode::

    import restpose
    server = restpose.Server('http://localhost:7777')
    doc = { 'text': 'Hello world', 'tag': 'A tag' }
    coll = server.collection("test_coll")
    coll.add_doc(doc, doc_type="blurb", doc_id=1)

And then, searching those documents can be done by:

.. testcode::
    :hide:

    coll.checkpoint().wait()

.. doctest::

    >>> s = coll.doc_type("blurb").field("text").text("Hello")
    >>> s.matches_estimated
    1
    >>> s[0].data == {'text': ['Hello world'],
    ...               'tag': ['A tag'],
    ...               'type': ['blurb'],
    ...               'id': ['1']}
    True

The rest of this overview goes through some of the subtle details and extra
features we just skipped over in that example.

Connecting to the server
------------------------

Once the server is running, it provides a REST API over HTTP.  The server runs
on port 7777 by default, and for the rest of this tutorial we'll assume that
it's running on the same machine as you're using the python client on, and is
running on the default port.

.. testcode::

    from restpose import Server
    server = Server('http://localhost:7777')

Adding a document
-----------------

As far as RestPose is concerned, a document is a set of fields, each of which
has a name, and each of which has one or more values.  Documents also have
types and IDs.  The document type is used to determine how each field should be
interpreted; the configuration of how to index and search each field can be
specified for each document type (though you will often be able to use
RestPose's default configuration).  The ID is used to identify the document,
and is unique within a given type.

IDs must be specified when sending a document to the RestPose server; the
python client currently doesn't automatically allocate IDs if they are missing.

Documents are stored within collections, which are just named groups of
documents.  It is not currently possible to search transparently across
multiple collections.  Collections should be used when you have independent
projects, but wish to share the resources of a server across them.

.. testcode::

    doc = { 'text': 'Hello world', 'tag': 'A tag' }
    coll = server.collection("test_coll")
    coll.add_doc(doc, doc_type="blurb", doc_id=1)

If all goes well, within a short time (usually a fraction of a second), the
document will have been indexed.  However, using the above calls the changes
won't be fully applied until a few seconds later (by default, until 5 seconds
of inactivity), and the new document will be available for searching until this
has occurred.  This delay is deliberate, and is to allow bulk updates to be
performed efficiently, but can be avoided using a checkpoint.

Checkpoints
-----------

Documents are added asynchronously; it's important to realise that the
:meth:`add_doc <restpose.client.Collection.add_doc>` function will only report
an error if it is unable to insert the document into the indexing queue on the
server (eg, because the server is down, or overloaded).  It will not report an
error if the document is invalid in some way, and the document will not
immediately be available for searching.

In addition, documents are processed in parallel; if I add document A and then
add document B, it is quite possible for processing of document B to finish
before processing of document A.

There is of course, a way to check for errors, to ensure the ordering of
particular modification operations and also to ensure that changes are made
ready for searching without the usual wait for inactivity.  These tasks are all
performed using :class:`CheckPoints <restpose.client.CheckPoint>`.

    >>> checkpt = coll.checkpoint().wait()
    >>> checkpt.total_errors, checkpt.errors, checkpt.reached
    (0, [], True)

Essentially, what's happening here is that the checkpoint is put into the
indexing queue in such a way that it will be processed only when all tasks
placed onto the queue before it have been completed, and that it will be
processed before any tasks placed onto the query after it are started.  When it
is processed, the preceding changes are committed (ie, made available for
searching).

The :meth:`wait <restpose.client.CheckPoint.wait>` method blocks until the
checkpoint has been processed.  Alternatively, if you don't want to block, the
checkpt.reached property will reflect the current state of the checkpoint on
the server.

.. note:: Currently, the server doesn't support long-polling for checkpoint
	  status, so the wait() method is implemented by polling the server
	  periodically.  This implementation is likely to be improved in
	  future.

It is also possible to make a checkpoint which doesn't cause a commit, in
order to collect errors and control ordering of processing operations.  To do
this, simply pass `commit=False` to the :meth:`Collection.checkpoint
<restpose.client.Collection.checkpoint>` method when creating the checkpoint.

Field types
-----------

.. todo:: This section needs rewriting for clarity (sorry!).

There are many different ways in which the data supplied in a field can be
processed and made available for searching.  The way in which each field is
indexed is controlled by the collection configuration, and can be adjusted
separately for each document type.

Essentially, the configuration maps each field name to a field type, and
associates various parameters with those field types.

Additionally, when a new field is seen (ie, one for which the configuration
doesn't have an entry), the configuration contains a list of patterns which
are applied in order, and the first match is used to configure the new field.

Currently, the RestPose Python client doesn't provide much support to help
you work with collection configuration; it just provides a mechanism for
getting and setting the full configuration as a hierarchical structure.  The
full configuration of a collection may be obtained from the server using the
the :meth:`Collection.config <restpose.client.Collection.config>` property.
This may then be modifed and applied back to the property.  For example, to
add a pattern to the default configuration for a new document type (ie, to
the configuration which will be used when a new document type is seen for the
first time):

.. doctest::

    >>> c = coll.config
    >>> c['default_type']['patterns'].insert(0,
    ...    ['test',
    ...     {'group': 'T', 'max_length': 10, 'too_long_action': 'error',
    ...      'type': 'exact'}])
    >>> coll.config = c

After the above, adding a new document to the collection with a previously
unseen document type would cause the configuration for indexing the document
type to process a field called "test" for exact matching, in group "T", but
produce an error if any entries in the "test" field were longer than 10
characters.

Details of the field types available, the parameters which can be applied to
them, and the default list of patterns, are contained in the server
documentation: :ref:`restpose:types_and_schemas`.

Searching
---------

There are several ways to build up and perform a search in RestPose.  Here's a
simple example:

.. doctest::

    >>> search = coll.field('text').text('Hello')
    >>> print len(search)
    1
    >>> search[0].data
    {'text': ['Hello world'], 'tag': ['A tag'], 'type': ['blurb'], 'id': ['1']}

By convention, the word ``query`` is used in RestPose to refer to a set of
operations which can be used to match and associate a weight with a set of
documents.  The word ``search`` is then used as a noun to refer to an object
comprising a query, and any other options involved in performing the search
(for example, the offset of the first result to retrieve from the server, or
options controlling additional information to retrieve).  The word ``search``
is also used as a very to refer to the operation of performing a search.

Queries can be constructed in several ways.  Firstly, a query can be created
which searches the contents of a named field.

.. doctest::

   >>> query = coll.field.text.parse('Hello')

In this case, ``query`` will represent a query on the "text" field, and will
use the query parser configured for that field to build a query from the word
"Hello".  The query will also be bound to the collection ``coll``, so that when
it is performed, the entire collection will be searched.  We say that the
target of the query is the entire collection.

.. note:: if the field name is not a valid python identifier, or is stored in a
   variable, you can use an alternative syntax of calling the ``coll.field``
   property, passing the field name as a parameter.  For example:

      >>> query = coll.field('text').parse('Hello')

A query can also be created which is bound to a document type within a
collection; when such a query is performed, only documents of the given type
will be considered for matching.  For example, the following command will
produce a query which has a target of the "blurb" document type within the
collection.

.. doctest::

   >>> query = coll.doc_type('blurb').field('text').text('Hello')

A query can also be created which is bound to neither a document type nor a
collection; before such a query can be performed it must be given a target
(which can be done by combining it with a query which is already associated
with a target, or by explicitly setting a target using the :meth:`set_target
<restpose.query.Searchable.set_target>` method.).

.. doctest::

   >>> from restpose import Field
   >>> query = Field('text').text('Hello')

What's happening behind the scenes here is that the :meth:`field
<restpose.client.QueryTarget.field>` method and the ``Field`` factory produce a
:class:`FieldQuerySource <restpose.client.FieldQuerySource>` object, which
provides various methods for creating queries.

Some query types can be performed across all fields; for this, the ``AnyField``
factory can be used to create unbound queries, or the :meth:`any_field
<restpose.client.QueryTarget.any_field>` method can be used to create bound
queries on collections or document types.  The documentation for each query
type indicates whether it is valid to search across all fields with that query
type.

Primitive query types
~~~~~~~~~~~~~~~~~~~~~

There are several "primitive" query types other than the "text" type described
so far.  Most of these are only applicable to fields which have been configured
in particular ways.  For full details of the search options available in
RestPose, see the server documentation on :ref:`restpose:searches`; this
section will discuss how to construct each type of query in Python.

* .. automethod:: restpose.client.FieldQuerySource.text
     :noindex:

* .. automethod:: restpose.client.FieldQuerySource.parse
     :noindex:

* .. automethod:: restpose.client.FieldQuerySource.is_in
     :noindex:

* .. automethod:: restpose.client.FieldQuerySource.equals
     :noindex:

* .. automethod:: restpose.client.FieldQuerySource.range
     :noindex:

* .. automethod:: restpose.client.FieldQuerySource.is_descendant
     :noindex:

     See also: `Taxonomies and categories`_

* .. automethod:: restpose.client.FieldQuerySource.is_or_is_descendant
     :noindex:

     See also: `Taxonomies and categories`_

* .. automethod:: restpose.client.FieldQuerySource.exists
     :noindex:

* .. automethod:: restpose.client.FieldQuerySource.nonempty
     :noindex:

* .. automethod:: restpose.client.FieldQuerySource.empty
     :noindex:

* .. automethod:: restpose.client.FieldQuerySource.has_error
     :noindex:

.. Note:: it is perfectly possible to construct a query on a field which
   cannot be performed due to the way in which a field has been configured;
   many queries can only be performed on certain types of field.  If you do
   this, you'll get an error when you try to perform the search, not when you
   construct the query.

There are also a couple of primitive query types which aren't specific to a
field, and can be created by methods of :class:`Collection
<restpose.client.Collection>` or :class:`DocumentType
<restpose.client.DocumentType>`.

* .. automethod:: restpose.client.QueryTarget.all
      :noindex:

* .. automethod:: restpose.client.QueryTarget.none
      :noindex:

Combining queries
~~~~~~~~~~~~~~~~~

Queries can be combined using several operators to build a query tree.  These
operators can be used to produce various boolean combinations of matching
results, and also to influence the way in which weights are combined.

There are many ways in which queries can be combined; the simplest to describe
are the boolean operations:

* Boolean AND

  A query can be constructed which only returns documents which match all of a
  set of subqueries.

  .. autoclass:: restpose.query.And
      :noindex:

  Such a query can also be constructed by joining two queries with the ``&``
  operator:

  .. automethod:: restpose.query.Query.__and__
      :noindex:

* Boolean OR

  A query can be constructed which only returns documents which match all of a
  set of subqueries.

  .. autoclass:: restpose.query.Or
      :noindex:

  Such a query can also be constructed by joining two queries with the ``|``
  operator:

  .. automethod:: restpose.query.Query.__or__
      :noindex:

* Boolean AND-NOT

  Rather than supporting a unary NOT operator (which would return all documents
  not matched by a query), RestPose implement an "AndNot" operator, which
  returns documents which match one query, but do not match another query.
  
  The lack of a unary NOT operator is because it is not generally possible to
  efficiently compute a list of all the documents in a Collection which do not
  match a query with the datastructures in use by RestPose.  Also, because it
  is difficult to associate useful scores with documents matching a unary NOT
  operator, it is rarely desirable to implement a unary NOT operator.  If you
  really need a unary NOT, you can use an ``all`` query as part of the AndNot
  operator.

  To construct a query which returns documents which match one query, but do
  not match any of a set of other queries:

  .. autoclass:: restpose.query.AndNot
      :noindex:

  Such a query can also be constructed by joining two queries with the ``-``
  operator:

  .. automethod:: restpose.query.Query.__sub__
      :noindex:

* Filter

  A filter query is a query which returns documents and weights from an initial
  query, but removes any documents which do not match another query (or set of
  queries).
  
  The ``Filter`` constructor allows a query to be constructed which returns
  documents which match all of a set of subqueries, but only returns the weight
  from the first of these subqueries.

  .. autoclass:: restpose.query.Filter
      :noindex:

  Such a query can also be constructed by joining two queries with the
  ``filter`` method:

  .. automethod:: restpose.query.Query.filter
      :noindex:

* AndMaybe

  An AndMaybe query is a query which returns only those documents which match
  an initial query, but adds weights from a set of other subqueries.  This can
  be used to adjust weights based on external factors (for example, matching
  tags), without causing extra documents to match the query.

  The ``AndMaybe`` constructor allows a query to be constructed which returns
  documents which match all of a set of subqueries, but only returns the weight
  from the first of these subqueries.

  .. autoclass:: restpose.query.AndMaybe
      :noindex:

  Such a query can also be constructed by joining two queries with the
  ``and_maybe`` method:

  .. automethod:: restpose.query.Query.and_maybe
      :noindex:

* Weight multiplication and division

  The weights returned from a query can be modified by multiplying them by a
  constant (positive) factor.  This can be used to bias the results from part
  of a combined query over the results from other parts of a combined query.

  The ``MultWeight`` constructor allows a query to be constructed which returns
  exactly the same documents as a subquery, but with the weight multiplied by a
  factor.

  .. autoclass:: restpose.query.MultWeight
      :noindex:

  Such a query can also be constructed by use of the ``*`` operator, applied to
  a positive number and a query (the query may be either on the right hand or
  left hand side):

  .. automethod:: restpose.query.Query.__mul__

  Weights can also be divided using the ``/`` operator.

* Boolean XOR

  Finally, RestPose also supports an XOR operator - this is rarely of much
  practical use, but is included for completeness of boolean operators.

  A query can be constructed which only returns documents which match an odd
  number of a set of subqueries.

  .. autoclass:: restpose.query.Xor
      :noindex:

  Such a query can also be constructed by joining two queries with the ``^``
  operator:

  .. automethod:: restpose.query.Query.__xor__
      :noindex:


Performing searches
~~~~~~~~~~~~~~~~~~~

Now you've done all this work to get a query, you'll almost certainly want to
perform a search using it.  Fortunately, this is very easy.

If you wish to control exactly when a search is sent to the server, you can
perform a search directly using the :meth:`search
<restpose.client.QueryTarget.search>` method on a Collection or DocumentType.
This returns a :class:`SearchResults <restpose.query.SearchResults>` object
which provides convenient access to the results as returned from the server.

However, an alternative approach which is often more convenient is also
provided: Query objects can be sliced and subscripted to get at the list of
matching documents.  They also support various methods and properties to get
statistics about things like the number of matching documents.  Communication
with the server will be performed when necessary, and the results of such
communication will be cached.

For example, suppose we have a query such as:

>>> query = coll.field('text').text('Hello')

To get the first result of a query:

>>> print query[0]
SearchResult(rank=0, data={'text': ['Hello world'], 'tag': ['A tag'], 'type': ['blurb'], 'id': ['1']})

Suppose you want the top 10 results.  One approach would be to subscript the
query with 0, 1, 2, etc.  This will actually be fairly efficient - the Python
RestPose client will request pages of results when it doesn't know how many
results you're going to want (the default page size is 20, but this can be
adjusted by changing the :attr:`page_size
<restpose.query.Searchable.page_size>` property).  You can even iterate over
all matching documents using the standard python iteration mechanism; the
iterator will return SearchResult objects.

>>> for r in query: print r
SearchResult(rank=0, data={'text': ['Hello world'], 'tag': ['A tag'], 'type': ['blurb'], 'id': ['1']})

To get just the first 10 results of the query, you can slice the query; this
returns a :class:`TerminalQuery <restpose.query.TerminalQuery>`, which has all
the same properties for performing searches as the other Query classes we've
discussed so far, but may not be combined with other Query objects.  The
TerminalQuery can be subscripted and iterated, but (unless the slice has an
open upper end) you are guaranteed that the results will be requested from the
server in a single page of size and offset governed by the slice.
:class:`Query <restpose.query.Query>` and :class:`TerminalQuery
<restpose.query.TerminalQuery>` have a common base class of :class:`Searchable
<restpose.query.Searchable>`.

The Xapian search engine, used by RestPose, implements some sophisticated
optimisations for calculating the top results of a query without having to
calculate all the possible documents matching a query.  To give these
optimisations as much scope to work as possible, you should usually slice your
query before accessing individual search results.

To get the total number of matching documents, you can use the ``len`` builtin
on a Query object.  This will cause a search to be performed if necessary, and
will return the exact number of matching documents.  However, again, if you do
not need the exact number of matching documents, you can allow the Xapian
optimisations to work a lot better by using a set of properties which produce
an estimate and bounds on the number of matching documents.  Specifically:

* the :attr:`matches_lower_bound
  <restpose.query.Searchable.matches_lower_bound>` property returns a lower
  bound on the number of matching documents.

* the :attr:`matches_estimated <restpose.query.Searchable.matches_estimated>`
  property returns an estimate of the number of matching documents.

* the :attr:`matches_upper_bound
  <restpose.query.Searchable.matches_upper_bound>` property returns an upper
  bound on the number of matching documents.

* the :attr:`estimate_is_exact
  <restpose.query.Searchable.estimate_is_exact>` property returns True if the
  estimate produced by ``matches_estimated`` is known to be the exact number of
  matching documents.

* the :attr:`has_more <restpose.query.Searchable.has_more>` property returns
  True if there are any matches after the slice represented by the Searchable.
  This can be useful for paginating.  (If the slice is open-ended, or the
  Searchable hasn't been sliced, this returns False).

It is possible to influence how much work Xapian performs when searching to
calculate the number of matching documents.  This can be done using the
:meth:`check_at_least <restpose.query.Searchable.check_at_least>` method, which
produces a new :class:`TerminalQuery <restpose.query.TerminalQuery>` with the
supplied ``check_at_least`` value.  When the search is performed, Xapian will
check at least this number of documents for being potential matches to the
search (if there are sufficient matches).  This ensures that the estimate and
bounds will be exact if fewer documents match than the supplied number; higher
``check_at_least`` values will increase the accuracy of the estimate, but will
reduce the speed at which the search is performed.

Setting the ``check_at_least`` value can also be useful when calculating
additional match information, such as counting term occurrence, and faceting.

Another useful property is the :attr:`total_docs
<restpose.query.Searchable.total_docs>` property, which returns the number of
documents in the target of the search (ie, in the DocumentType or Collection
searched).

Taxonomies and categories
-------------------------

You may have noticed the :meth:`is_descendant
<restpose.client.FieldQuerySource.is_descendant>` and
:meth:`is_or_is_descendant
<restpose.client.FieldQuerySource.is_or_is_descendant>` methods above.  These
allow you to take advantage of the taxonomy feature of RestPose, which allows
you to define a hierarchy of categories, and to search for documents in which a
value is not only an exact match for a category, but also to search for
documents in which a value is an exact match for any of the descendants of a
category.

The taxonomy structure (ie, the hierarchy of categories) is stored in the
collection, and associated with a name.  To get a list of the defined
taxonomies in a collection, you can use the :meth:`Collection.taxonomies
<restpose.client.Collection.taxonomies>` method, which returns a list of names:

.. doctest::

   >>> taxonomy_names = coll.taxonomies()

To build up a taxonomy, you can make a Taxonomy object from a collection:

.. doctest::

   >>> taxonomy = coll.taxonomy('my_taxonomy')

Parent-child relationships between categories can then be built up using the
:meth:`add_parent <restpose.client.Taxonomy.add_parent>` and
:meth:`remove_parent <restpose.client.Taxonomy.remove_parent>` calls.

.. doctest::

   >>> taxonomy.add_parent('child_cat', 'parent_cat')
   {}
   >>> taxonomy.remove_parent('child_cat', 'parent_cat')
   {}

Individual categories can be added or removed using the :meth:`add_category
<restpose.client.Taxonomy.add_category>` and :meth:`remove_category
<restpose.client.Taxonomy.remove_category>` methods.

The list of top level categories (ie, those without parents) can be retrieved
using :meth:`top <restpose.client.Taxonomy.top>`, and individual category
details can be retrieved with :meth:`get_category
<restpose.client.Taxonomy.get_category>`

These calls can be performed at any time - any document updates which need to
be made to reflect the new hierarchy will be performed as necessary.

.. note:: If possible, it is better to put the hierarchy in place before adding
          documents, since this will require less work in total.

.. note:: Currently, the taxonomy feature is not designed to perform well with
	  large numbers of entries in the category hierarchy (ie, more than a
	  few hundred entries).  Performance improvements are planned, but if
	  you need to use the feature with deep hierarchies, contact the author
	  on IRC or email.

Additional information (Facets, Term occurrence)
------------------------------------------------

Often, it is useful to be able to get additional information along with a
search result; for example, in a faceted search application, it is desirable to
get counts of the number of matching documents which have each value of a
field, which are then used to display options for narrowing down the search.

Currently, RestPose supports getting two types of additional information:
occurrence counts for terms, and co-occurrence counts for terms.  While the
occurrence counts feature could be used to support a faceted search interface,
it wouldn't perform particularly well, because it is fairly slow to access the
term occurrence counts.  More efficient support for faceted search (involving
storing the required information in a slot allowing for faster access) will be
implemented in a future release; if you have urgent need of it, contact the
author on IRC (in #restpose on irc.freenode.net).

Term occurrence
~~~~~~~~~~~~~~~

RestPose can calculate counts of each term seen in matching documents.  To do
this, use `calc_occur` on the Searchable to indicate that the information
should be calculated during the search.

.. automethod:: restpose.query.Searchable.calc_occur
    :noindex:

The occurrence counts can then be retrieved via the :attr:`Searchable.info
<restpose.query.Searchable.info>` property.  Note that it is usually advisable
to set the ``check_at_least`` value for such a search, to ensure that a
reasonable number of potential matches will be included when calculating the
occurrence counts.  Conversely, because calculating this requires access to the
termlists for each document observed, which is a slow operation, the
`calc_occur` method allows you to limit the number of documents checked using
the `doc_limit` parameter; you can set this to get a sampling of the documents
in the index, rather than potentially checking all of them (note that such a
sampling isn't unbiased, unfortunately; the documents which are sampled will be
the ones nearer the start of the index, which usually means those documents
which were indexed first).

Term co-occurrence
~~~~~~~~~~~~~~~~~~

Similarly, Restpose can calculate counts of which term-pairs occur together
most often.  To do this, use `calc_cooccur` on the Searchable to indicate that
the information should be calculated during the search.

.. automethod:: restpose.query.Searchable.calc_cooccur
    :noindex:

The same options as when calculating term occurrence counts apply for
controlling the number of documents considered when calculating this
information.  Note that calculating this is significantly more expensive than
calculating the pure occurrence counts, so in a large system you might well
want to start with small limits, and gradually increase the counts until
performance is no longer acceptable.

Realisers: associating search results with external objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In many situations, the search index is built from objects which are stored in
an external database.  When this is the case, it is desirable to be able to
associate a search result with the object in the database which it represents.
For example, in a Django project, a search index might be built up by
processing objects from the Django ORM, and it would be desirable for templates
to be able to access the appropriate ORM object directly, rather than just
being able to access the fields stored in the search engine.

This can of course be done manually, but the RestPose client provides some
support to make this cleaner and more convenient.  In brief: searches can be
provided with a "realiser" function, which is called when neccessary to look up
the objects associated with a set of results; these objects can then be
accessed via the `SearchResult.object` property.

FIXME - document how to set realiser functions

FIXME - document what realiser functions need to do

FIXME - give an example realiser for use with Django
