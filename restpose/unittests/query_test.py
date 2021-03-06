# -*- coding: utf-8 -
#
# This file is part of the restpose python module, released under the MIT
# license.  See the COPYING file for more information.

from unittest import TestCase
from .. import query, And, Or, Xor, AndNot, Filter, AndMaybe
import operator

class DummyTarget(object):
    """A stub target that just remembers the query structure last passed to it.
    """
    last = None
    count = 0
    def search(self, search):
        self.last = search
        self.count = self.count + 1
        return query.SearchResults({
                                    'from': search.get('from', 0),
                                    'size_requested': search.get('size', 0),
                                    'check_at_least': search.get('check_at_least', 0),
                                   })


class QueryTest(TestCase):
    maxDiff = 10000
    def check_target(self, target, expected_last):
        self.assertEqual(target.count, 1)
        self.assertEqual(target.last, expected_last)
        target.count = 0
        
    def test_ops(self):
        target = DummyTarget()
        q = query.QueryField("fieldname", "is", "10", target)

        self.assertEqual(q.matches_lower_bound, 0)
        self.assertEqual(q.matches_estimated, 0)
        self.assertEqual(q.matches_upper_bound, 0)
        self.assertEqual(q._results.offset, 0)
        self.assertEqual(q._results.size_requested, 20)
        self.assertEqual(q._results.check_at_least, 21)
        self.assertEqual(q._results.items, [])
        self.assertEqual(q._results.info, [])
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'field': ['fieldname', 'is', '10']},
                           'size': 20,
                          })

        qm = q * 3.14
        qm.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'scale': {'factor': 3.14,
                             'query': {'field': ['fieldname', 'is', '10']}}},
                           'size': 20,
                          })

        q2 = query.QueryField("fieldname", "is", "11", target)
        q3 = query.QueryField("fieldname", "is", "12", target)

        q1 = qm | q2
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'or': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']}
                           ]},
                           'size': 20,
                          })

        q1 = Or(qm, q2, q3)
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'or': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']},
                             {'field': ['fieldname', 'is', '12']}
                           ]},
                           'size': 20,
                          })

        q1 = qm & q2
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'and': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']}
                           ]},
                           'size': 20,
                          })

        q1 = And(qm, q2, q3)
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'and': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']},
                             {'field': ['fieldname', 'is', '12']}
                           ]},
                           'size': 20,
                          })

        q1 = qm ^ q2
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'xor': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']}
                           ]},
                           'size': 20,
                          })

        q1 = Xor(qm, q2, q3)
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'xor': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']},
                             {'field': ['fieldname', 'is', '12']}
                           ]},
                           'size': 20,
                          })

        q1 = qm - q2
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'and_not': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']}
                           ]},
                           'size': 20,
                          })

        q1 = AndNot(qm, q2, q3)
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'and_not': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']},
                             {'field': ['fieldname', 'is', '12']}
                           ]},
                           'size': 20,
                          })

        q1 = qm.filter(q2)
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'filter': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']}
                           ]},
                           'size': 20,
                          })

        q1 = Filter(qm, q2, q3)
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'filter': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']},
                             {'field': ['fieldname', 'is', '12']}
                           ]},
                           'size': 20,
                          })

        q1 = qm.and_maybe(q2)
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'and_maybe': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']}
                           ]},
                           'size': 20,
                          })

        q1 = AndMaybe(qm, q2, q3)
        q1.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'and_maybe': [
                             {'scale': {'factor': 3.14,
                               'query': {'field': ['fieldname', 'is', '10']}
                             }},
                             {'field': ['fieldname', 'is', '11']},
                             {'field': ['fieldname', 'is', '12']}
                           ]},
                           'size': 20,
                          })

        qm = 2 * q
        qm.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'scale': {'factor': 2,
                             'query': {'field': ['fieldname', 'is', '10']}}},
                           'size': 20,
                          })

        qm = q / 2
        qm.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'scale': {'factor': 0.5,
                             'query': {'field': ['fieldname', 'is', '10']}}},
                           'size': 20,
                          })

        # operator.div doesn't exist in python 3, but we don't need to test the
        # behaviour of / there, because it uses truediv anyway.
        if hasattr(operator, 'div'):
            qm = operator.div(q, 2)
            qm.matches_estimated
            self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'scale': {'factor': 0.5,
                             'query': {'field': ['fieldname', 'is', '10']}}},
                           'size': 20,
                          })

        qm = operator.truediv(q, 2)
        qm.matches_estimated
        self.check_target(target,
                          {
                           'check_at_least': 21,
                           'query': {'scale': {'factor': 0.5,
                             'query': {'field': ['fieldname', 'is', '10']}}},
                           'size': 20,
                          })

    def test_slices(self):
        target = DummyTarget()
        q = query.QueryField("fieldname", "is", "10", target)

        def chk(target, from_=0, size=None, check_at_least=None):
            expected = { 'query': {'field': ['fieldname', 'is', '10']} }
            if from_ != 0:
                expected['from'] = from_
            if size is None:
                size = 20
            expected['size'] = size
            if check_at_least:
                expected['check_at_least'] = check_at_least
            self.check_target(target, expected)

        q.check_at_least(7).matches_estimated
        # Checks for at least the first page
        chk(target, check_at_least=21)

        q.check_at_least(22).matches_estimated
        # Checks for a whole page
        chk(target, check_at_least=22)

        q[:10].check_at_least(7).matches_estimated
        # Checks for a whole page
        chk(target, size=10, check_at_least=11)

        # Check slices with each end set or not set.
        q[10:20].matches_estimated
        chk(target, from_=10, size=10, check_at_least=21)

        q[10:].matches_estimated
        chk(target, from_=10, check_at_least=31)

        q[:10].matches_estimated
        chk(target, from_=0, size=10, check_at_least=11)

        q[:].matches_estimated
        chk(target, from_=0, check_at_least=21)


        # Check negative indexes.
        self.assertRaises(IndexError, q.__getitem__, slice(-1, None))
        self.assertRaises(IndexError, q.__getitem__, slice(None, -1))


        # Check (mostly invalid) step values
        self.assertRaises(IndexError, q.__getitem__, slice(0, None, 0))
        self.assertRaises(IndexError, q.__getitem__, slice(0, None, 2))
        q[0::1].matches_estimated
        chk(target, from_=0, check_at_least=21)

        # Check invalid index
        self.assertRaises(TypeError, q.__getitem__, "bad index")


        # Check all types of subslice for a slice with stat and end set.
        q[10:20][3:5].matches_estimated
        chk(target, from_=13, size=2, check_at_least=16)

        q[10:20][3:10].matches_estimated
        chk(target, from_=13, size=7, check_at_least=21)

        q[10:20][3:15].matches_estimated
        chk(target, from_=13, size=7, check_at_least=21)

        q[10:20][3:].matches_estimated
        chk(target, from_=13, size=7, check_at_least=21)

        q[10:20][:5].matches_estimated
        chk(target, from_=10, size=5, check_at_least=16)

        q[10:20][:10].matches_estimated
        chk(target, from_=10, size=10, check_at_least=21)

        q[10:20][:20].matches_estimated
        chk(target, from_=10, size=10, check_at_least=21)

        q[10:20][:].matches_estimated
        chk(target, from_=10, size=10, check_at_least=21)


        # Check all types of subslice for a slice with only the start set.
        q[10:][3:5].matches_estimated
        chk(target, from_=13, size=2, check_at_least=16)

        q[10:][3:10].matches_estimated
        chk(target, from_=13, size=7, check_at_least=21)

        q[10:][3:15].matches_estimated
        chk(target, from_=13, size=12, check_at_least=26)

        q[10:][3:].matches_estimated
        chk(target, from_=13, check_at_least=34)

        q[10:][:5].matches_estimated
        chk(target, from_=10, size=5, check_at_least=16)

        q[10:][:10].matches_estimated
        chk(target, from_=10, size=10, check_at_least=21)

        q[10:][:15].matches_estimated
        chk(target, from_=10, size=15, check_at_least=26)

        q[10:][:20].matches_estimated
        chk(target, from_=10, size=20, check_at_least=31)

        q[10:][:].matches_estimated
        chk(target, from_=10, check_at_least=31)


        # Check all types of subslice for a slice with only the end set.
        q[:10][3:5].matches_estimated
        chk(target, from_=3, size=2, check_at_least=6)

        q[:10][3:10].matches_estimated
        chk(target, from_=3, size=7, check_at_least=11)

        q[:10][3:15].matches_estimated
        chk(target, from_=3, size=7, check_at_least=11)

        q[:10][3:].matches_estimated
        chk(target, from_=3, size=7, check_at_least=11)

        q[:10][:5].matches_estimated
        chk(target, from_=0, size=5, check_at_least=6)

        q[:10][:10].matches_estimated
        chk(target, from_=0, size=10, check_at_least=11)

        q[:10][:15].matches_estimated
        chk(target, from_=0, size=10, check_at_least=11)

        q[:10][:20].matches_estimated
        chk(target, from_=0, size=10, check_at_least=11)

        q[:10][:].matches_estimated
        chk(target, from_=0, size=10, check_at_least=11)


        # Check all types of subslice for a slice with neither start or end
        # set.
        q[:][10:20].matches_estimated
        chk(target, from_=10, size=10, check_at_least=21)

        q[:][10:].matches_estimated
        chk(target, from_=10, check_at_least=31)

        q[:][:10].matches_estimated
        chk(target, from_=0, size=10, check_at_least=11)

        q[:][:].matches_estimated
        chk(target, from_=0, check_at_least=21)

    def test_no_target(self):
        """Test behaviour of a query for which no target is set.

        """
        q = query.QueryField("fieldname", "is", "10")
        self.assertRaises(ValueError, getattr, q, 'matches_estimated')
