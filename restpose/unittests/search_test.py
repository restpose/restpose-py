# -*- coding: utf-8 -
#
# This file is part of the restpose python module, released under the MIT
# license.  See the COPYING file for more information.

from .helpers import RestPoseTestCase
from ..query import SearchResult
from ..resource import RestPoseResource
from .. import Server, Field, AnyField, \
 Searchable, Query, \
 ResourceNotFound, RequestFailed
from restkit import ResourceError
import sys

class LogResource(RestPoseResource):
    """A simple resource which logs requests.

    This could be tidied up and made into a useful debugging tool in future,
    but for now it's just used to test supplying a custom resource instance to
    the Server() class.

    """
    def __init__(self, *args, **kwargs):
        super(LogResource, self).__init__(*args, **kwargs)
        self.log = []

    def request(self, method, path=None, *args, **kwargs):
        try:
            res = super(LogResource, self).request(method, path=path,
                                                   *args, **kwargs)
        except ResourceError:
            e = sys.exc_info()[1] # Python 2/3 compatibility
            self.log.append("%s: %s -> %d %s" % (method, path, e.status_int, e))
            raise
        self.log.append("%s: %s -> %d" % (method, path, int(res.status[:3])))
        return res

    def clone(self):
        res = super(LogResource, self).clone()
        res.log = self.log
        return res


class SearchTest(RestPoseTestCase):
    maxDiff = 10000

    expected_item_data =  {
        'cat': ['greeting'],
        'empty': [''],
        'id': ['1'],
        'tag': ['A tag'],
        'text': ['Hello world'],
        'type': ['blurb'],
    }

    # Expected items for tests which return a single result
    expected_items_single = [
        SearchResult(rank=0, data=expected_item_data, results="dummy"),
    ]

    def check_results(self, results, offset=0, size_requested=None, check_at_least=0,
                      matches_lower_bound=None,
                      matches_estimated=None,
                      matches_upper_bound=None,
                      items = [],
                      info = []):
        if size_requested is None:
            size_requested = 10 # server default
        if matches_lower_bound is None:
            matches_lower_bound = len(items)
        if matches_estimated is None:
            matches_estimated = len(items)
        if matches_upper_bound is None:
            matches_upper_bound = len(items)

        if isinstance(results, Searchable):
            results = results.search()
        self.assertEqual(results.offset, offset)
        self.assertEqual(results.size_requested, size_requested)
        self.assertEqual(results.check_at_least, check_at_least)
        self.assertEqual(results.matches_lower_bound, matches_lower_bound)
        self.assertEqual(results.matches_estimated, matches_estimated)
        self.assertEqual(results.matches_upper_bound, matches_upper_bound)
        self.assertEqual(len(results.items), len(items))
        for i in range(len(items)):
            self.assertEqual(results.items[i].rank, items[i].rank)
            self.assertEqual(results.items[i].data, items[i].data)
        self.assertEqual(results.info, info)

    @classmethod
    def setup_class(cls):
        doc = { 'text': 'Hello world', 'tag': 'A tag', 'cat': "greeting",
                'empty': "", 'test': 'too long' * 10 }
        coll = Server().collection("test_coll")
        coll.delete()
        coll.checkpoint().wait()

        # Add a "test" field which errors if too long, to test error searches.
        c = coll.config
        c['default_type']['patterns'].insert(0,
            ['test',
             {'group': 'T', 'max_length': 10, 'too_long_action': 'error',
              'type': 'exact'}])
        coll.config = c

        coll.add_doc(doc, doc_type="blurb", doc_id="1")
        chk = coll.checkpoint().wait()
        assert chk.total_errors == 1

    def setUp(self):
        self.coll = Server().collection("test_coll")

    def test_indexed_ok(self):
        """Check that setup put the database into the desired state.

        """
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        gotdoc = self.coll.get_doc("blurb", "1")
        self.assertEqual(gotdoc.data, {
                                      'cat': ['greeting'],
                                      'empty': [''],
                                      'id': ['1'],
                                      'tag': ['A tag'],
                                      'text': ['Hello world'],
                                      'type': ['blurb'],
                                      })
        self.assertEqual(gotdoc.terms, {
                                      '\\tblurb\\t1': {},
                                      '!\\tblurb': {},
                                      '#\\tE': {},
                                      '#\\tEtest': {},
                                      '#\\tFcat': {},
                                      '#\\tFempty': {},
                                      '#\\tFtag': {},
                                      '#\\tFtest': {},
                                      '#\\tFtext': {},
                                      '#\\tM': {},
                                      '#\\tMempty': {},
                                      '#\\tN': {},
                                      '#\\tNcat': {},
                                      '#\\tNtag': {},
                                      '#\\tNtest': {},
                                      '#\\tNtext': {},
                                      'Zt\\thello': {'wdf': 1},
                                      'Zt\\tworld': {'wdf': 1},
                                      'c\\tCgreeting': {},
                                      'g\\tA tag': {},
                                      't\\thello': {'positions': [1], 'wdf': 1},
                                      't\\tworld': {'positions': [2], 'wdf': 1},
                                      })
        self.assertEqual(gotdoc.values, {
            '0': '\\x05Etest'
                 '\\x04Fcat\\x06Fempty\\x04Ftag\\x05Ftest\\x05Ftext'
                 '\\x06Mempty\\x04Ncat\\x04Ntag\\x05Ntest\\x05Ntext',
            '1': '\\x05blurb',
            '268435588': '\\x08greeting',
            '268435592': '\\x05A tag',
        })

    def test_getdoc(self):
        """Test that getting bits of a document works.

        """
        # Get the same document 3 times, and trigger lazy fetching by a
        # different method each time.
        d1 = self.coll.get_doc("blurb", "1")
        d1.data
        d2 = self.coll.get_doc("blurb", "1")
        d2.terms
        d3 = self.coll.get_doc("blurb", "1")
        d3.values
        self.assertEqual(d1.data, d2.data)
        self.assertEqual(d1.data, d3.data)
        self.assertEqual(d1.terms, d2.terms)
        self.assertEqual(d1.terms, d3.terms)
        self.assertEqual(d1.values, d2.values)
        self.assertEqual(d1.values, d3.values)

    def test_field_is(self):
        q = self.coll.doc_type("blurb").field('tag') == 'A tag'
        results = q.search()
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field('tag').equals('A tag')
        results = q.search()
        self.check_results(results, items=self.expected_items_single)

    def test_field_is_in(self):
        """Test an is_in query."""
        q = self.coll.doc_type("blurb").field.tag.is_in(['A tag', 'A bag'])
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field.tag.is_in(['A flag', 'A bag'])
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").field.id.is_in([1, 3])
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field.id.is_in([2, 3])
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

    def test_field_is_in_string(self):
        """Test special case of is_in when a string is supplied."""
        q = self.coll.doc_type("blurb").field.tag.is_in('A tag')
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field.tag.is_in('A bag')
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").field.id.is_in(1)
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field.id.is_in(2)
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

    def test_field_exists(self):
        q = self.coll.doc_type("blurb").any_field.exists()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field.tag.exists()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field('id').exists()
        # ID field is not stored, so searching for its existence returns
        # nothing.
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").find(Field.type.exists())
        # Type field is not stored, so searching for its existence returns
        # nothing.
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").field.missing.exists()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

    def test_field_empty(self):
        q = self.coll.doc_type("blurb").find(AnyField.empty())
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field.empty.empty()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field('text').empty()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").find(Field.id.empty())
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").find(Field('type').empty())
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").field.missing.empty()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

    def test_field_nonempty(self):
        q = self.coll.doc_type("blurb").any_field.nonempty()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").field.empty.nonempty()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").field('text').nonempty()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

        q = self.coll.doc_type("blurb").find(Field.id.nonempty())
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").find(Field('type').nonempty())
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

        q = self.coll.doc_type("blurb").field.missing.nonempty()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

    def test_field_has_error(self):
        results = self.coll.doc_type("blurb").any_field.has_error()
        self.check_results(results, items=self.expected_items_single)

        results = self.coll.field('test').has_error()
        self.check_results(results, items=self.expected_items_single)

        results = self.coll.field.text.has_error()
        self.check_results(results, items=[])

    def test_query_all(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

    def test_query_none(self):
        q = self.coll.doc_type("blurb").none()
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=[])

    def test_calc_cooccur(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.calc_cooccur('t', ''))
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        self.check_results(results, check_at_least=1,
                           items=self.expected_items_single,
                           info=[{
                               'counts': [['hello', 'world', 1]],
                               'docs_seen': 1,
                               'terms_seen': 2,
                               'group': 't',
                               'prefix': '',
                               'type': 'cooccur'
                           }])
        self.assertEqual(q.calc_cooccur('t', '').info,
                         [{
                             'counts': [['hello', 'world', 1]],
                             'docs_seen': 1,
                             'terms_seen': 2,
                             'group': 't',
                             'prefix': '',
                             'type': 'cooccur'
                         }])

    def test_calc_occur(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.calc_occur('t', ''))
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        self.check_results(results, check_at_least=1,
                           items=self.expected_items_single,
                           info=[{
                               'counts': [['hello', 1], ['world', 1]],
                               'docs_seen': 1,
                               'group': 't',
                               'terms_seen': 2,
                               'prefix': '',
                               'type': 'occur'
                           }])

    def test_tag_facet_count(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.calc_facet_count('tag'))
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        self.check_results(results, check_at_least=1,
                           items=self.expected_items_single,
                           info=[{
                               'counts': [['A tag', 1]],
                               'docs_seen': 1,
                               'fieldname': 'tag',
                               'type': 'facet_count',
                               'values_seen': 1,
                           }])

    def test_cat_facet_count(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.calc_facet_count('cat'))
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        self.check_results(results, check_at_least=1,
                           items=self.expected_items_single,
                           info=[{
                               'counts': [['greeting', 1]],
                               'docs_seen': 1,
                               'fieldname': 'cat',
                               'type': 'facet_count',
                               'values_seen': 1,
                           }])

    def test_type_facet_count(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.calc_facet_count('type'))
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        self.check_results(results, check_at_least=1,
                           items=self.expected_items_single,
                           info=[{
                               'counts': [['blurb', 1]],
                               'docs_seen': 1,
                               'fieldname': 'type',
                               'type': 'facet_count',
                               'values_seen': 1,
                           }])

    def test_text_facet_count(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.calc_facet_count('text'))
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        self.check_results(results, check_at_least=0,
                           items=self.expected_items_single,
                           info=[{
                               'counts': [],
                               'docs_seen': 0, # Count of 0 because no stored
                                               # facets for text fields
                               'fieldname': 'text',
                               'type': 'facet_count',
                               'values_seen': 0,
                           }])


    def test_empty_facet_count(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.calc_facet_count('empty'))
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        self.check_results(results, check_at_least=0,
                           items=self.expected_items_single,
                           info=[{
                               'counts': [],
                               'docs_seen': 0, # Count of 0 because this is a
                                               # text field.
                               'fieldname': 'empty',
                               'type': 'facet_count',
                               'values_seen': 0,
                           }])

    def test_missing_facet_count(self):
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.calc_facet_count('missing'))
        self.assertEqual(self.coll.status.get('doc_count'), 1)
        self.check_results(results, check_at_least=0,
                           items=self.expected_items_single,
                           info=[{
                               'counts': [],
                               'docs_seen': 0, # Count of 0 because no field
                                               # configuration for this field.
                               'fieldname': 'missing',
                               'type': 'facet_count',
                               'values_seen': 0,
                           }])

    def test_raw_query(self):
        results = self.coll.doc_type("blurb").search(dict(query=dict(matchall=True)))

        # if size isn't specified in the query, uses the server's page size,
        # which is 10.
        self.check_results(results, items=self.expected_items_single,
                           size_requested=10)

    def test_query_adjust_offset(self):
        """Test adjusting the configured offset for a search.

        """
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q[1:])
        self.check_results(results, offset=1,
                           matches_lower_bound=1,
                           matches_estimated=1,
                           matches_upper_bound=1,
                           items=[])
        # Check that the adjustment didn't change the original search.
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

    def test_query_adjust_size(self):
        """Test adjusting the configured size for a search.

        """
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q[:1])
        self.check_results(results, size_requested=1,
                           items=self.expected_items_single)
        # Check that the adjustment didn't change the original search.
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

    def test_query_adjust_check_at_least(self):
        """Test adjusting the configured check_at_least value for a search.

        """
        q = self.coll.doc_type("blurb").all()
        results = self.coll.doc_type("blurb").search(q.check_at_least(1))
        self.check_results(results, check_at_least=1,
                           items=self.expected_items_single)
        # Check that the adjustment didn't change the original search.
        results = self.coll.doc_type("blurb").search(q)
        self.check_results(results, items=self.expected_items_single)

    def test_resource_log_search(self):
        "Test runnning a search, using a special resource to log requests."
        # The URI is required, but will be replaced by that passed to Server()
        logres = LogResource(uri='http://127.0.0.1:7777/')

        coll = Server(resource_instance=logres).collection("test_coll")
        doc = { 'text': 'Hello world', 'tag': 'A tag', 'cat': "greeting",
                'empty': "" }
        coll.add_doc(doc, doc_type="blurb", doc_id="1")
        self.wait(coll)
        self.assertTrue(len(logres.log) >= 3)
        self.assertEqual(logres.log[0],
                         'PUT: /coll/test_coll/type/blurb/id/1 -> 202')
        self.assertEqual(logres.log[1],
                         'POST: /coll/test_coll/checkpoint -> 201')
        self.assertEqual(logres.log[2][:32],
                         'GET: /coll/test_coll/checkpoint/')
        self.assertEqual(logres.log[2][-6:], '-> 200')

        # Try making the server using resource_class instead of instance
        coll = Server(resource_class=LogResource).collection("test_coll")
        logres = coll._resource
        doc = coll.doc_type('blurb').get_doc('2')
        self.assertRaises(ResourceNotFound, getattr, doc, 'data')
        self.assertEqual(logres.log,
                         ['GET: /coll/test_coll/type/blurb/id/2 -> ' +
                          '404 No document found of type "blurb" and id "2"'])

    def test_server_status(self):
        """Test the result of getting the server status."""
        server = Server()
        s = server.status
        self.assertTrue('tasks' in s)
        self.assertTrue('search' in s['tasks'])
        # No reason to test further, since this is just the structure returned
        # by the server.

    def test_search_on_unknown_type(self):
        """Test that a search on an unknown document type returns exactly the
        same results as a search on a known document type.

        """
        coll = Server().collection("test_coll")
        coll.add_doc({}, doc_type="empty_type", doc_id="1")
        coll.delete_doc(doc_type="empty_type", doc_id="1")
        self.wait(coll)
        empty_type = coll.doc_type("empty_type")
        missing_type = coll.doc_type("missing_type")
        empty_query = empty_type.all()
        missing_query = missing_type.all()

        self.assertEqual(empty_type.search(empty_query[7:18]
                                           .check_at_least(3))._raw,
                         missing_type.search(missing_query[7:18]
                                             .check_at_least(3))._raw)

        self.assertEqual(empty_type.search(empty_query[7:18]
                                           .check_at_least(3)
                                           .calc_cooccur('', ''))._raw,
                         missing_type.search(missing_query[7:18]
                                             .check_at_least(3)
                                             .calc_cooccur('', ''))._raw)

    def test_query_subscript(self):
        """Test subscript on a query.

        """
        q = self.coll.doc_type("blurb").all()
        self.assertEqual(q[0].data, self.expected_item_data)

    def test_field_text(self):
        """Test a text search."""
        q = self.coll.doc_type("blurb").field.text.text("Hello world")
        self.assertEqual(q[0].data, self.expected_item_data)

        # Default operator is phrase, so adding a word in the middle produces
        # no results.
        q = self.coll.doc_type("blurb").field.text.text("Hello cold world")
        self.assertRaises(IndexError, q.__getitem__, 0)

        # Try with server-default for the operator.
        q = self.coll.doc_type("blurb").field.text.text("Hello cold world",
                                                        op=None)
        self.assertRaises(IndexError, q.__getitem__, 0)

        # Try with operator of or instead.
        q = self.coll.doc_type("blurb").field.text.text("Hello cold world",
                                                        op="or")
        self.assertEqual(q[0].data, self.expected_item_data)

        # Try with an invalid operator
        q = self.coll.doc_type("blurb").field.text.text("Hello cold world",
                                                        op="invalid")
        self.assertRaises(RequestFailed, q.__getitem__, 0)

        # Try with a larger window
# FIXME - disabled, because window sizes don't work on field_text searches,
# currently.
#        q = self.coll.doc_type("blurb").field_text("text", "Hello cold world",
#                                                   window=3)
#        self.assertEqual(q[0].data, self.expected_item_data)

    def test_field_parse(self):
        """Test a parsed field search."""
        t = self.coll.doc_type("blurb")
        q = t.field.text.parse("Hello world")
        self.assertEqual(q[0].data, self.expected_item_data)

        # Default operator is and, so adding a word in the middle produces
        # no results.
        q = t.field.text.parse("Hello cold world")
        self.assertRaises(IndexError, q.__getitem__, 0)

        # Try with server-default for the operator.
        q = t.field.text.parse("Hello cold world", op=None)
        self.assertRaises(IndexError, q.__getitem__, 0)

        # Try with operator of or instead.
        q = t.field.text.parse("Hello cold world", op="or")
        self.assertEqual(q[0].data, self.expected_item_data)

        # Try with an invalid operator
        q = t.field.text.parse("Hello cold world", op="invalid")
        self.assertRaises(RequestFailed, q.__getitem__, 0)


class LargeSearchTest(RestPoseTestCase):
    """Tests of handling results of searches which return lots of results.

    """
    maxDiff = 10000

    @staticmethod
    def make_doc(num, type="num"):
        return { 'num': [num], 'id': [str(num)], 'type': [type] }

    @classmethod
    def setup_class(cls):
        coll = Server().collection("test_coll")
        coll.delete()
        coll.checkpoint().wait()
        for num in range(193):
            doc = cls.make_doc(num)
            coll.add_doc(doc, doc_type="num", doc_id=str(num))
        for num in range(50):
            doc = cls.make_doc(num, "other")
            coll.add_doc(doc, doc_type="other", doc_id=str(num))
        chk = coll.checkpoint().wait()
        assert chk.total_errors == 0

    def setUp(self):
        self.coll = Server().collection("test_coll")

    def test_indexed_ok(self):
        """Check that setup put the database into the desired state.

        """
        self.assertEqual(self.coll.status.get('doc_count'), 243)
        gotdoc = self.coll.get_doc("num", "77")
        self.assertEqual(gotdoc.data, {
                                      'num': [77],
                                      'id': ['77'],
                                      'type': ['num'],
                                      })
        self.assertEqual(gotdoc.terms, {
                                      '\\tnum\\t77': {},
                                      '!\\tnum': {},
                                      '#\\tFnum': {},
                                      '#\\tN': {},
                                      '#\\tNnum': {},
                                      })
        self.assertEqual(gotdoc.values, { '0': '\\x04Fnum\\x04Nnum',
                                          '1': '\\x03num',
                                          '268435599': '\\x02\\xb8\\xd0' })

        gotdoc = self.coll.get_doc("other", "17")
        self.assertEqual(gotdoc.data, {
                                      'num': [17],
                                      'id': ['17'],
                                      'type': ['other'],
                                      })

    def test_query_empty(self):
        q = self.coll.none()
        self.assertRaises(IndexError, q.__getitem__, 0)
        q = self.coll.doc_type("num").none()
        self.assertRaises(IndexError, q.__getitem__, 0)

    def test_query_order_by_field_coll(self):
        """Test setting the result order to be by a field.

        """
        q = self.coll.doc_type("num").all()
        q1 = q.order_by('num') # default order is ascending
        self.assertEqual(q1[0].data, self.make_doc(0))
        self.assertEqual(q1[192].data, self.make_doc(192))
        q1 = q.order_by('num', True) 
        self.assertEqual(q1[0].data, self.make_doc(0))
        self.assertEqual(q1[192].data, self.make_doc(192))
        q1 = q.order_by('num', False) 
        self.assertEqual(q1[0].data, self.make_doc(192))
        self.assertEqual(q1[192].data, self.make_doc(0))
        self.assertRaises(IndexError, q1.__getitem__, 193)

    def test_query_order_by_field(self):
        """Test setting the result order to be by a field.

        """
        q = self.coll.all()
        self.assertEqual(q.total_docs, 243)
        # The order of items with the same num is undefined, so just check the
        # nums.
        q1 = q.order_by('num') # default order is ascending
        self.assertEqual(q1[0].data['num'], [0])
        self.assertEqual(q1[1].data['num'], [0])
        self.assertEqual(q1[98].data['num'], [49])
        self.assertEqual(q1[99].data['num'], [49])
        self.assertEqual(q1[100].data['num'], [50])
        self.assertEqual(q1[101].data['num'], [51])
        self.assertEqual(q1[242].data, self.make_doc(192))
        self.assertRaises(IndexError, q1.__getitem__, 243)
        q1 = q.order_by('num', True) 
        self.assertEqual(q1[0].data['num'], [0])
        self.assertEqual(q1[1].data['num'], [0])
        self.assertEqual(q1[242].data, self.make_doc(192))
        self.assertRaises(IndexError, q1.__getitem__, 243)
        q1 = q.order_by('num', False) 
        self.assertEqual(q1[0].data, self.make_doc(192))
        self.assertEqual(q1[1].data, self.make_doc(191))
        self.assertEqual(q1[242].data['num'], [0])
        self.assertRaises(IndexError, q1.__getitem__, 243)

        # Test using multiple keys
        q1 = q.order_by_multiple([['num', False]]) 
        self.assertEqual(q1[0].data, self.make_doc(192))
        self.assertEqual(q1[1].data, self.make_doc(191))
        self.assertEqual(q1[242].data['num'], [0])
        self.assertRaises(IndexError, q1.__getitem__, 243)

        q1 = q.order_by_multiple([['num', True]]) 
        self.assertEqual(q1[0].data['num'], [0])
        self.assertEqual(q1[1].data['num'], [0])
        self.assertEqual(q1[242].data, self.make_doc(192))
        self.assertRaises(IndexError, q1.__getitem__, 243)

        q1 = q.order_by_multiple([['type', False], ['num', True]]) 
        self.assertEqual(q1[0].data['type'], ['other'])
        self.assertEqual(q1[0].data['num'], [0])
        self.assertEqual(q1[1].data['type'], ['other'])
        self.assertEqual(q1[1].data['num'], [1])
        self.assertEqual(q1[49].data['type'], ['other'])
        self.assertEqual(q1[49].data['num'], [49])
        self.assertEqual(q1[50].data['type'], ['num'])
        self.assertEqual(q1[50].data['num'], [0])
        self.assertEqual(q1[242].data, self.make_doc(192))
        self.assertRaises(IndexError, q1.__getitem__, 243)

        q1 = q.order_by_multiple([['type', True], ['num', True]]) 
        self.assertEqual(q1[0].data, self.make_doc(0))
        self.assertEqual(q1[1].data, self.make_doc(1))
        self.assertEqual(q1[192].data, self.make_doc(192))
        self.assertEqual(q1[193].data['type'], ['other'])
        self.assertEqual(q1[193].data['num'], [0])
        self.assertEqual(q1[242].data['type'], ['other'])
        self.assertEqual(q1[242].data['num'], [49])
        self.assertRaises(IndexError, q1.__getitem__, 243)

        q1 = q.order_by_multiple([['num', True], ['type', True]]) 
        self.assertEqual(q1[0].data, self.make_doc(0))
        self.assertEqual(q1[1].data['type'], ['other'])
        self.assertEqual(q1[1].data['num'], [0])
        self.assertEqual(q1[2].data, self.make_doc(1))
        self.assertEqual(q1[242].data, self.make_doc(192))
        self.assertRaises(IndexError, q1.__getitem__, 243)

    def test_query_all(self):
        q = self.coll.doc_type("num").all().order_by('num')

        self.assertEqual(q[0].data, self.make_doc(0))
        self.assertEqual(q[1].data, self.make_doc(1))
        self.assertEqual(q[50].data, self.make_doc(50))
        self.assertEqual(q[192].data, self.make_doc(192))
        self.assertRaises(IndexError, q.__getitem__, 193)
        self.assertEqual(len(q), 193)
        self.assertEqual(q.total_docs, 193)

        qs = q[10:20]
        self.assertEqual(qs[0].data, self.make_doc(10))
        self.assertEqual(qs[1].data, self.make_doc(11))
        self.assertEqual(qs[9].data, self.make_doc(19))
        self.assertRaises(IndexError, qs.__getitem__, 10)
        self.assertRaises(IndexError, qs.__getitem__, -1)
        self.assertEqual(len(qs), 10)

        qs = q[190:200]
        self.assertEqual(qs[0].data, self.make_doc(190))
        self.assertEqual(qs[1].data, self.make_doc(191))
        self.assertEqual(qs[2].data, self.make_doc(192))
        self.assertRaises(IndexError, qs.__getitem__, 3)
        self.assertRaises(IndexError, qs.__getitem__, -1)
        self.assertEqual(len(qs), 3)

        qs = q[15:]
        self.assertEqual(qs[0].data, self.make_doc(15))
        self.assertEqual(qs[50 - 15].data, self.make_doc(50))
        self.assertEqual(qs[192 - 15].data, self.make_doc(192))
        self.assertRaises(IndexError, qs.__getitem__, 193 - 15)
        self.assertEqual(len(qs), 193 - 15)

    def test_query_range(self):
        dt = self.coll.doc_type('num')
        q = dt.field.num.range(46, 50)
        q1 = dt.field('num').range(46, 50)
        self.assertEqual(q._query, q1._query)
        self.assertEqual(q._target, q1._target)
        q1 = dt.find(Field.num.range(46, 50))
        self.assertEqual(q._query, q1._query)
        self.assertEqual(q._target, q1._target)
        q1 = dt.find(Field('num').range(46, 50))
        self.assertEqual(q._query, q1._query)
        self.assertEqual(q._target, q1._target)

        self.assertEqual(len(q), 5)
        q = q.order_by('num')
        self.assertEqual(q[0].data, self.make_doc(46))
        self.assertEqual(q[4].data, self.make_doc(50))
        self.assertRaises(IndexError, q.__getitem__, 5)

    def test_query_iteration(self):
        q = self.coll.doc_type("num").field.num.range(46, 50) \
                .order_by('num')
        self.assertEqual(list(item.data['num'][0] for item in q),
                         [46, 47, 48, 49, 50])
        self.assertEqual(list(item.data['num'][0] for item in iter(q)),
                         [46, 47, 48, 49, 50])

    def test_query_filter(self):
        q = self.coll.field('num').range(46, 50)
        self.assertEqual(len(q), 9) # num has 46-50, other has 46-49
        q1 = q.filter(Field.type.equals('num'))
        q2 = q.filter(self.coll.find(Field.type.equals('num')))
        self.assertEqual(q1._query, q2._query)
        self.assertEqual(q1._target, q2._target)
        self.assertEqual(len(q1), 5)

    def test_has_more(self):
        q = self.coll.field('num').range(46, 50)
        self.assertEqual(q.has_more, False)
        self.assertEqual(q[:5].has_more, True)
        self.assertEqual(q[:8].has_more, True)
        self.assertEqual(q[:9].has_more, False)
        self.assertEqual(q[:10].has_more, False)
        self.assertEqual(len(q), 9)

    def test_fromdoc(self):
        q = self.coll.doc_type('num').field.num.range(10, 100).order_by('num')
        self.assertEqual(len(q), 91)
        q1 = q.fromdoc('num', '60', -5, 10)
        self.assertEqual(len(q1), 10)
        self.assertEqual(q1[0].rank, 45)
        self.assertEqual(q1[0].data['num'][0], 55)
        q2 = q1[5:]
        self.assertEqual(len(q2), 5)
        self.assertEqual(q2[0].rank, 50)
        self.assertEqual(q2[0].data['num'][0], 60)
        q2 = q1[5:6]
        self.assertEqual(len(q2), 1)
        self.assertEqual(q2[0].rank, 50)
        self.assertEqual(q2[0].data['num'][0], 60)
        self.assertRaises(ValueError, q[:10].fromdoc, 'num', '60', -5, 10)
        self.assertRaises(ValueError, q[10:].fromdoc, 'num', '60', -5, 10)
        self.assertRaises(RequestFailed,
                          q.fromdoc('num', '110', -5, 10).__getitem__, 0)
        self.assertRaises(RequestFailed,
                          q.fromdoc('num', '2000', -5, 10).__getitem__, 0)
