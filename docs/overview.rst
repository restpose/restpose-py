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

    >>> s = coll.doc_type("blurb").field_text("text", "Hello")
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

.. note:: Currently, the server doesn't support long-polling, so the wait()
	  method is implemented by polling the server periodically.  This
	  implementation is likely to be improved in future.

It is also possible to make a checkpoint which doesn't cause a commit, in order
to collect errors and control ordering of processing operations.  To do this,
simply pass `commit=False` to the :meth:`Collection.checkpoint
<restpose.client.Collection.checkpoint>` method when creating the checkpoint.

Searching
---------

.. todo:: Document the ways in which searches can be created, and the ways in which results can be accessed.


Field types
-----------

.. todo:: Document how field types are picked automatically, and point to the comprehensive documentation of the field types in the main restpose docs.

Facets
------

.. todo:: Document how to get facets, and how to make searches from them.
