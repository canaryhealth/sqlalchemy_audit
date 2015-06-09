# -*- coding: utf-8 -*-
import morph
import unittest

from sqlalchemy import create_engine

from ..auditable import Auditable
from .reservation import Base, Session


class DbTestCase(unittest.TestCase):
  engine = create_engine('sqlite://', echo=True)

  def setUp(self):
    super(DbTestCase, self).setUp()
    Base.metadata.create_all(self.engine)
    Session.configure(bind=self.engine)
    self.session = Session()
    Auditable.auditable_session(self.session)


  def tearDown(self):
    super(DbTestCase, self).tearDown()
    self.session.close()
    Base.metadata.drop_all(self.engine)


  def assertSeqEqual(self, result, expected, pick=None):
    '''
    Helper method to compare two sequences. If `pick` is specified, then it 
    would only compares those attributes for each object.
    '''
    if pick is not None and morph.isseq(result) and morph.isseq(expected):
      result = [morph.pick(item, *morph.tolist(pick)) for item in result]
      expected = [morph.pick(item, *morph.tolist(pick)) for item in expected]

    print '=== result ==='
    print result
    print '=== expected ==='
    print expected

    self.assertEqual(result, expected, 'the sequences are different')
