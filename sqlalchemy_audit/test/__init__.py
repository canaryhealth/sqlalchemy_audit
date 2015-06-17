# -*- coding: utf-8 -*-
import morph
import time
import unittest
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.declarative.base import _declarative_constructor as SaInit

from ..versioned import Versioned

engine = None
def setup_module():
  global engine
  engine = sa.create_engine('sqlite://', echo=False)


class DbTestCase(unittest.TestCase):
  def setUp(self):
    super(DbTestCase, self).setUp()
    self.session = sa.orm.Session(engine)
    self.Base = sa.ext.declarative.declarative_base()    
    Versioned.versioned_session(self.session)


  def tearDown(self):
    super(DbTestCase, self).tearDown()
    self.session.close()
    sa.orm.clear_mappers()
    self.Base.metadata.drop_all(engine)


  def create_tables(self):
    self.Base.metadata.create_all(engine)


  def make_reservation(self):
    '''
    Creates (makes) class Reservation for tests
    '''
    # note: this may appear a bit weird, but my intent is to keep the 
    #       declarations within instantiated scope so that the teardown is 
    #       thorough (for the mappers, metadata, etc)
    class Reservation(Versioned, self.Base):
      __tablename__ = 'reservations'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, nullable=False)
      name = sa.Column(sa.String)
      date = sa.Column(sa.Date)
      time = sa.Column(sa.Time)
      party = sa.Column(sa.Integer)

      def __init__(self, *args, **kwargs):
        self.id = str(uuid.uuid4())
        self.created = time.time()
        SaInit(self, *args, **kwargs)

      def __repr__(self):
        return '<Reservation(id="%s", rev_id="%s", created="%s", name="%s", date="%s", time="%s", party="%s">' % (self.id, self.rev_id, self.created, self.name, self.date, self.time, self.party)

    Reservation.broadcast_crud()
    self.create_tables()
    return Reservation


  def assertSeqEqual(self, result, expected, pick=None):
    '''
    Helper method to compare two sequences. If `pick` is specified, then it 
    would only compares those attributes for each object.
    '''
    if pick is not None and morph.isseq(result) and morph.isseq(expected):
      result = [morph.pick(item, *morph.tolist(pick)) for item in result]
      expected = [morph.pick(item, *morph.tolist(pick)) for item in expected]

    # print '=== result ==='
    # print result
    # print '=== expected ==='
    # print expected

    self.assertEqual(result, expected, 'the sequences are different')
