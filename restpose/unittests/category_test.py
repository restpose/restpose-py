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

def listdoc(doc):
    def l(v):
        if hasattr(v, '__iter__'):
            return v
        return [v]
    return dict((k, l(v)) for (k, v) in doc.iteritems()) 

def make_doc(num, id=None, type=None):
    doc = { 'tag': 'A tag', 'cat': str(num), 'cat2': str(num + 1) }
    if id is not None:
        doc['id'] = id
    if type is not None:
        doc['type'] = type
    return doc

def docdata(num):
    return listdoc(make_doc(num, id=str(num), type='test'))

def idsfrom(query):
    return ','.join(sorted(x.data['id'][0] for x in query))

class CategoryTest(RestPoseTestCase):
    maxDiff = 10000


    @classmethod
    def setup_class(cls):
        coll = Server().collection("test_coll")
        coll.delete()
        coll.checkpoint().wait()

        # Configure the category field.
        c = coll.config
        c['default_type']['patterns'].insert(0,
            ['cat',
             {'group': 'c',
              'taxonomy': 'my_taxonomy',
              'max_length': 32,
              'store_field': 'cat',
              'too_long_action': 'hash',
              'type': 'cat'}])
        c['default_type']['patterns'].insert(0,
            ['cat2',
             {'group': 'c2',
              'taxonomy': 'my_taxonomy',
              'max_length': 32,
              'store_field': 'cat2',
              'too_long_action': 'hash',
              'type': 'cat'}])
        coll.config = c

    def test_cat_is(self):
        """Test that searching for a category value works.

        """

        coll = Server().collection("test_coll")

        # Add some documents
        target = coll.doc_type("test")
        for doc_id in range(10):
            target.add_doc(make_doc(doc_id), doc_id=doc_id)

        chk = coll.checkpoint().wait()
        self.assertEqual(chk.total_errors, 0)

        # Check that setup put the database into the desired state.
        self.assertEqual(coll.status.get('doc_count'), 10)
        gotdoc = coll.get_doc("test", "1")
        self.assertEqual(gotdoc.data, docdata(1))
        self.assertEqual(gotdoc.terms, {
                                      '\\ttest\\t1': {},
                                      '!\\ttest': {},
                                      '#\\tFcat': {},
                                      '#\\tFcat2': {},
                                      '#\\tFtag': {},
                                      '#\\tN': {},
                                      '#\\tNcat': {},
                                      '#\\tNcat2': {},
                                      '#\\tNtag': {},
                                      'c\\tC1': {},
                                      'c2\\tC2': {},
                                      'g\\tA tag': {},
                                      })
        self.assertEqual(gotdoc.values, {
                         u'0': u'\\x04Fcat\\x05Fcat2\\x04Ftag\\x04Ncat\\x05Ncat2\\x04Ntag',
                         u'1': u'\\x04test',
                         u'268435592': u'\\x05A tag',
        })

        # Test some category searches.
        r = coll.field.cat.equals("1")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].data, docdata(1))
        self.assertEqual(coll.taxonomies(), [])

        self.assertEqual(idsfrom(coll.field.cat.is_descendant('2')), '')
        self.assertEqual(idsfrom(coll.field.cat.is_or_is_descendant('2')), '2')

        # Add an entry to a taxonomy
        t = coll.taxonomy('my_taxonomy')
        self.assertEqual(t.name, 'my_taxonomy')
        self.assertRaises(ResourceNotFound, t.all)
        t.add_category('1')
        self.assertEqual(coll.checkpoint().wait().errors, [])
        self.assertEqual(coll.taxonomies(), ['my_taxonomy'])
        self.assertEqual(t.all(), {'1': []})

        # Remove an entry from a taxonomy
        t.remove_category('1')
        self.assertEqual(coll.checkpoint().wait().errors, [])
        self.assertEqual(coll.taxonomies(), ['my_taxonomy'])
        self.assertEqual(t.all(), {})

        # Add a parent to an entry
        t.add_parent('1', '2')
        self.assertEqual(coll.checkpoint().wait().errors, [])
        self.assertEqual(coll.taxonomies(), ['my_taxonomy'])
        self.assertEqual(t.all(), {'1': ['2'], '2': []})

        # Check that the document has been reindexed appropriately.
        gotdoc = coll.get_doc("test", "1")
        self.assertEqual(gotdoc.data, docdata(1))
        self.assertEqual(gotdoc.terms, {
                                      '\\ttest\\t1': {},
                                      '!\\ttest': {},
                                      '#\\tFcat': {},
                                      '#\\tFcat2': {},
                                      '#\\tFtag': {},
                                      '#\\tN': {},
                                      '#\\tNcat': {},
                                      '#\\tNcat2': {},
                                      '#\\tNtag': {},
                                      'c\\tC1': {},
                                      'c\\tA2': {},
                                      'c2\\tC2': {},
                                      'g\\tA tag': {},
                                      })
        self.assertEqual(gotdoc.values, {
            '0': '\\x04Fcat\\x05Fcat2\\x04Ftag\\x04Ncat\\x05Ncat2\\x04Ntag',
            '1': '\\x04test',
            '268435592': '\\x05A tag',
        })

        # Add a document when categories exist
        target = coll.doc_type("test")
        target.delete_doc(1)
        target.add_doc(make_doc(1), doc_id=1)
        self.assertEqual(coll.checkpoint().wait().errors, [])
        gotdoc2 = coll.get_doc("test", "1")
        # Check that it's the same as a document added before the category was
        # made.
        self.assertEqual(gotdoc.data, gotdoc2.data)
        self.assertEqual(gotdoc.terms, gotdoc2.terms)
        self.assertEqual(gotdoc.values, gotdoc2.values)

        # Try a category search
        self.assertEqual(idsfrom(coll.field.cat.is_descendant('2')), '1')
        self.assertEqual(idsfrom(coll.field.cat.is_or_is_descendant('2')),
                         '1,2')

        # Get the top categories
        self.assertEqual(coll.taxonomy('my_taxonomy').top(),
                         {'2': {'child_count': 1, 'descendant_count': 1}})
        self.assertEqual(coll.taxonomy('my_taxonomy').get_category('2'),
                         {'ancestors': [], 'children': ['1'],
                          'descendants': ['1'], 'parents': []})
        self.assertEqual(coll.taxonomy('my_taxonomy').get_category('1'),
                         {'ancestors': ['2'], 'children': [],
                          'descendants': [], 'parents': ['2']})

        # Remove an entry from a taxonomy
        t.remove_parent('1', '2')
        self.assertEqual(coll.checkpoint().wait().errors, [])
        self.assertEqual(coll.taxonomies(), ['my_taxonomy'])
        self.assertEqual(t.all(), {'1': [], '2': []})
        self.assertEqual(coll.taxonomy('my_taxonomy').top(),
                         {'1': {'child_count': 0, 'descendant_count': 0},
                          '2': {'child_count': 0, 'descendant_count': 0},
                         })
        self.assertEqual(coll.taxonomy('my_taxonomy').get_category('1'),
                         {'ancestors': [], 'children': [],
                          'descendants': [], 'parents': []})
        self.assertEqual(coll.taxonomy('my_taxonomy').get_category('2'),
                         {'ancestors': [], 'children': [],
                          'descendants': [], 'parents': []})

        self.assertEqual(idsfrom(coll.field.cat.is_descendant('2')), '')
        self.assertEqual(idsfrom(coll.field.cat.is_or_is_descendant('2')), '2')
        gotdoc2 = coll.get_doc("test", "1")
        self.assertEqual(gotdoc.data, gotdoc2.data)
        terms = gotdoc.terms
        del terms['c\\tA2']
        self.assertEqual(terms, gotdoc2.terms)
        self.assertEqual(gotdoc.values, gotdoc2.values)

        # Test removing the entire taxonomy
        t.add_parent('1', '2')
        t.remove_category('2')
        self.assertEqual(coll.checkpoint().wait().errors, [])
        self.assertEqual(t.all(), {'1': []})
        gotdoc2 = coll.get_doc("test", "1")
        self.assertEqual(gotdoc.data, gotdoc2.data)
        self.assertEqual(terms, gotdoc2.terms)
        self.assertEqual(gotdoc.values, gotdoc2.values)

        t.remove()
        self.assertEqual(coll.checkpoint().wait().errors, [])
        self.assertEqual(coll.taxonomies(), [])
        self.assertRaises(ResourceNotFound, t.all)

        self.assertEqual(idsfrom(coll.field.cat.is_descendant('2')), '')
        self.assertEqual(idsfrom(coll.field.cat.is_or_is_descendant('2')), '2')

    def test_cat_hier_mod(self):
        """Test that some modifications of the hierarchy don't cause problems.

        Suppose we have categories A, B, C, D.
         - A is made parent of B and C
         - B is made a parent of D
         - C is made a parent of D
         - C is removed as a parent of D
         - Test that D is still marked as a descendant of A

        """
        coll = Server().collection("test_coll")
        target = coll.doc_type("test2")
        target.add_doc({'cat': 'D'}, doc_id='1')
        tax = coll.taxonomy('my_taxonomy')
        tax.add_parent('B', 'A')
        tax.add_parent('C', 'A')
        tax.add_parent('D', 'B')
        tax.add_parent('D', 'C')

        self.assertEqual(coll.checkpoint().wait().total_errors, 0)
        doc = target.get_doc('1')
        self.assertEqual(doc.terms, {
            '!\\ttest2': {},
            '#\\tFcat': {},
            '#\\tN': {},
            '#\\tNcat': {},
            '\\ttest2\\t1': {},
            'c\\tAA': {},
            'c\\tAB': {},
            'c\\tAC': {},
            'c\\tCD': {},
        })
        tax.remove_parent('D', 'C')
        self.assertEqual(coll.checkpoint().wait().total_errors, 0)

        doc = target.get_doc('1')
        self.assertEqual(doc.terms, {
            '!\\ttest2': {},
            '#\\tFcat': {},
            '#\\tN': {},
            '#\\tNcat': {},
            '\\ttest2\\t1': {},
            'c\\tAA': {},
            'c\\tAB': {},
            'c\\tCD': {},
        })

        self.assertEqual(coll.checkpoint().wait().total_errors, 0)
        target.delete_doc('1')
        tax.remove()
        self.assertEqual(coll.checkpoint().wait().total_errors, 0)
