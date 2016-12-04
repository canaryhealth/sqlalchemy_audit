# -*- coding: utf-8 -*-
import time
import unittest
import uuid

import morph
import sqlalchemy as sa
from sqlalchemy.ext import associationproxy
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


  def make_user_keyword(self):
    class User(Versioned, self.Base):
      __tablename__ = 'user'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float)
      name = sa.Column(sa.String)
      keywords = sa.ext.associationproxy.association_proxy(
        'user_keyword', 'keyword',
        creator=lambda kw: UserKeyword(keyword=kw))
      def __init__(self, *args, **kwargs):
        super(User, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())
        self.created = time.time()

    class Keyword(Versioned, self.Base):
      __tablename__ = 'keyword'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float)
      word = sa.Column(sa.String)
      users = sa.ext.associationproxy.association_proxy(
        'user_keyword', 'user',
        creator=lambda usr: UserKeyword(user=usr))
      def __init__(self, *args, **kwargs):
        super(Keyword, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())
        self.created = time.time()

    class UserKeyword(Versioned, self.Base):
      __tablename__ = 'user_keyword'
      user_id = sa.Column(sa.String, sa.ForeignKey('user.id'),
                          primary_key=True)
      user = sa.orm.relationship(
        'User', 
        backref=sa.orm.backref('user_keyword', cascade='all, delete-orphan'))
      keyword_id = sa.Column(sa.String, sa.ForeignKey('keyword.id'),
                             primary_key=True)
      keyword = sa.orm.relationship(
        'Keyword',
        backref=sa.orm.backref('user_keyword', cascade='all, delete-orphan'))
      def __init__(self, *args, **kwargs):
        super(UserKeyword, self).__init__(*args, **kwargs)

    User.broadcast_crud()
    UserRev = User.Revision
    Keyword.broadcast_crud()
    KeywordRev = Keyword.Revision
    UserKeyword.broadcast_crud()
    UserKeywordRev = UserKeyword.Revision
    self.create_tables()
    return User, UserRev, Keyword, KeywordRev, UserKeyword, UserKeywordRev



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


  def assertCountUniqueValues(self, result, attr, expected_count):
    '''
    Helper method to validate the number of unique values in a collection.
    '''
    result_count = len(set([ getattr(x, attr) for x in result ]))
    self.assertEqual(result_count, expected_count)
