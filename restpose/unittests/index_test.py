# -*- coding: utf-8 -
#
# This file is part of the restpose python module, released under the MIT
# license.  See the COPYING file for more information.

from .helpers import RestPoseTestCase
from .. import Server, CheckPointExpiredError, ResourceNotFound
from ..client import CheckPoint
import sys

class IndexTest(RestPoseTestCase):

    def test_delete_db(self):
        """Test that deleting a database functions correctly.

        """
        coll = Server().collection("test_coll")
        coll.delete()
        doc = { 'text': 'Hello world', 'tag': 'A tag', 'cat': "greeting",
                'empty': "" }
        coll.add_doc(doc, doc_type="blurb", doc_id="1")
        self.wait(coll)
        self.assertEqual(coll.get_doc("blurb", "1").data,
                         dict(
                              cat = ['greeting'],
                              empty = [''],
                              id = ['1'],
                              tag = ['A tag'],
                              text = ['Hello world'],
                              type = ['blurb'],
                             ))

        self.assertTrue('test_coll' in Server().collections)

        coll.delete()

        # Need to set commit=False, or the checkpoint re-creates the
        # collection.
        self.wait(coll, commit=False)
        self.assertTrue('test_coll' not in Server().collections)
        msg = None
        try:
            coll.get_doc("blurb", "1").data
        except ResourceNotFound:
            e = sys.exc_info()[1] # Python 2/3 compatibility
            msg = e.msg
        self.assertEqual(msg, 'No collection of name "test_coll" exists')

    def test_delete_doc(self):
        """Test that deleting a document functions correctly.

        """
        coll = Server().collection("test_coll")
        coll.delete()

        # Check deleting a document via the collection.
        doc = { 'text': 'Hello world', 'tag': 'A tag', 'cat': "greeting",
                'empty': "" }
        coll.add_doc(doc, doc_type="blurb", doc_id="1")
        self.wait(coll)
        self.assertEqual(coll.get_doc("blurb", "1").data,
                         dict(
                              cat = ['greeting'],
                              empty = [''],
                              id = ['1'],
                              tag = ['A tag'],
                              text = ['Hello world'],
                              type = ['blurb'],
                             ))

        coll.delete_doc(doc_type="blurb", doc_id="1")
        self.wait(coll)
        msg = None
        try:
            coll.get_doc("blurb", "1").data
        except ResourceNotFound:
            e = sys.exc_info()[1] # Python 2/3 compatibility
            msg = e.msg
        self.assertEqual(msg, 'No document found of type "blurb" and id "1"')

        # Check deleting a document via the type object.
        t = coll.doc_type("blurb")
        t.add_doc(doc, doc_id="1")
        self.wait(coll)
        self.assertEqual(t.get_doc("1").data,
                         dict(
                              cat = ['greeting'],
                              empty = [''],
                              id = ['1'],
                              tag = ['A tag'],
                              text = ['Hello world'],
                              type = ['blurb'],
                             ))

        t.delete_doc(doc_id="1")
        self.wait(coll)
        msg = None
        try:
            t.get_doc("1").data
        except ResourceNotFound:
            e = sys.exc_info()[1] # Python 2/3 compatibility
            msg = e.msg
        self.assertEqual(msg, 'No document found of type "blurb" and id "1"')

    def test_index_id_or_type_errors(self):
        """Test that errors due to bad ID or type specifications when indexing
        are reported correctly.

        """
        coll = Server().collection("test_coll")
        coll.delete()
        doc = { 'text': 'test doc', 'type': 'foo', 'id': '1' }
        # All the following combinations should be successful.
        coll.add_doc(doc)
        doc['id'] = 2
        coll.add_doc(doc, doc_type='foo')
        doc['id'] = 3
        coll.add_doc(doc, doc_id=3)
        doc['id'] = 4
        coll.add_doc(doc, doc_id="4")
        doc['id'] = 5
        coll.add_doc(doc, doc_type="foo", doc_id=5)
        doc['id'] = "6"
        coll.add_doc(doc, doc_type="foo", doc_id=6)

        coll.add_doc(doc, doc_type='oof1') # Error: mismatched types
        coll.add_doc(doc, doc_id=12) # Error: mismatched ids
        coll.doc_type('oof2').add_doc(doc) # Error: mismatched types
        coll.add_doc(doc, doc_type='oof3', doc_id=13) # Error: mismatched types
        coll.doc_type('oof4').add_doc(doc, doc_id=14) # Error: mismatched types
        coll.doc_type('foo').add_doc(doc, doc_id=15) # Error: mismatched ids
        coll.add_doc(doc, doc_id=16) # Error: mismatched ids
        doc['id'] = [7,8]
        coll.add_doc(doc)
        del doc['type']
        coll.add_doc(doc) # Error: no type specified

        chk = coll.checkpoint().wait()
        self.assertEqual(chk.total_errors, 9)
        self.assertEqual(len(chk.errors), 9)
        def mkkey(x): return x.get('doc_id', '') + x.get('doc_type', '') + x.get('msg')
        expected_errors = [
            {'msg': 'Indexing error in field "type": "No document type supplied or stored in document."'},
            {'msg': 'Indexing error in field "type": "Document type supplied differs from that inside document."', 'doc_type': 'oof1'},
            {'msg': 'Indexing error in field "id": "Document id supplied (\'12\') differs from that inside document (\'6\')."', 'doc_id': '12'},
            {'msg': 'Indexing error in field "type": "Document type supplied differs from that inside document."', 'doc_type': 'oof2'},
            {'msg': 'Indexing error in field "type": "Document type supplied differs from that inside document."', 'doc_type': 'oof3', 'doc_id': '13'},
            {'msg': 'Indexing error in field "type": "Document type supplied differs from that inside document."', 'doc_type': 'oof4', 'doc_id': '14'},
            {'msg': 'Indexing error in field "id": "Document id supplied (\'15\') differs from that inside document (\'6\')."', 'doc_type': 'foo', 'doc_id': '15'},
            {'msg': 'Indexing error in field "id": "Document id supplied (\'16\') differs from that inside document (\'6\')."', 'doc_id': '16'},
            {'msg': 'Indexing error in field "id": "Multiple ID values provided - must have only one"'},
        ]
        self.assertEqual(sorted(chk.errors, key=mkkey),
                         sorted(expected_errors, key=mkkey))

        self.assertEqual(coll.get_doc('foo', '1').data,
                         dict(text=['test doc'], type=['foo'], id=['1']))
        self.assertEqual(coll.get_doc('foo', '2').data,
                         dict(text=['test doc'], type=['foo'], id=[2]))
        self.assertEqual(coll.get_doc('foo', '3').data,
                         dict(text=['test doc'], type=['foo'], id=[3]))
        self.assertEqual(coll.get_doc('foo', '4').data,
                         dict(text=['test doc'], type=['foo'], id=[4]))
        self.assertEqual(coll.get_doc('foo', '5').data,
                         dict(text=['test doc'], type=['foo'], id=[5]))
        self.assertEqual(coll.get_doc('foo', '6').data,
                         dict(text=['test doc'], type=['foo'], id=["6"]))

    def test_checkpoint(self):
        coll = Server().collection("test_coll")

        # Check that accessing the id works.
        c = coll.checkpoint(commit=False)
        id = c.check_id
        self.assertTrue(len(id) > 10)

        c = CheckPoint(coll, {'checkid': 'fake_checkid'})
        self.assertEqual(c.check_id, 'fake_checkid')
        self.assertRaises(CheckPointExpiredError, getattr, c, 'reached')
        self.assertRaises(CheckPointExpiredError, getattr, c, 'errors')
        self.assertRaises(CheckPointExpiredError, getattr, c, 'total_errors')
        self.assertRaises(CheckPointExpiredError, c.wait)

    def test_custom_config(self):
        coll = Server().collection("test_coll")
        coll.delete()
        self.wait(coll)
        config = coll.config
        self.assertEqual(config['format'], 3)
        self.assertEqual(list(config['types'].keys()), [])

        coll.config = {'types': {'foo': {
            'alpha': {'type': 'text'}
        }}}
        self.wait(coll, [{'msg': 'Setting collection config failed with ' +
                  'RestPose::InvalidValueError: Member format was missing'}])
        self.assertEqual(list(config['types'].keys()), [])
        coll.config = {'format': 3,
            'types': {'foo': {
                'alpha': {'type': 'text'}
            }}
        }
        self.wait(coll)
        config = coll.config
        self.assertEqual(config['format'], 3)
        self.assertEqual(list(config['types'].keys()), ['foo'])
        coll.delete()
        self.wait(coll)

    def test_get_name(self):
        coll = Server().collection("test_coll")
        self.assertEqual(coll.name, 'test_coll')
        t = coll.doc_type("blurb")
        self.assertEqual(t.name, 'blurb')
