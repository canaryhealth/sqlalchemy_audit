# -*- coding: utf-8 -*-
import datetime
import time
import unittest
import uuid

import sqlalchemy as sa
from canary.model.util import RestrictingForeignKey

from . import DbTestCase
from ..versioned import Versioned, DeleteForbidden, UpdateForbidden


class TestVersioned(DbTestCase):

  def test_rev_schema_creation(self):
    class A(Versioned, self.Base):
      __tablename__ = 'a'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, nullable=False)
      name = sa.Column(sa.String, default='a', nullable=False)
      b_id = sa.Column(sa.String, RestrictingForeignKey('b.id'), nullable=False)

    class B(self.Base):
      __tablename__ = 'b'
      id = sa.Column(sa.String, primary_key=True)
      name = sa.Column(sa.String)

    A.broadcast_crud()
    self.create_tables()

    self.assertEqual(A.__table__.c.rev_id.unique, True)

    result = A.Revision.__table__
    expected = sa.Table(
      'a_rev_prime', self.Base.metadata,
      sa.Column('rev_id', sa.String(length=36), primary_key=True),
      sa.Column('rev_created', sa.Float, nullable=False),
      sa.Column('rev_isdelete', sa.Boolean, default=False, nullable=False),
      sa.Column('id', sa.String, nullable=False),
      sa.Column('created', sa.Float, nullable=True),
      sa.Column('name', sa.String, default=None, nullable=True),
      sa.Column('b_id', sa.String, nullable=True)
    )

    for col in ('rev_isdelete', 'id', 'rev_id', 'created', 'name', 'b_id'):
      for prop in ('name', 'type', 'default', 'primary_key', 'nullable',
                   'foreign_keys'):
        result_col_prop = getattr(getattr(result.c, col), prop) 
        expected_col_prop = getattr(getattr(expected.c, col), prop)
        # todo: figure out these "hacks"
        # `type`, `default` are returned as a method, hence the repr to get it 
        # to compare
        if prop in ('type', 'default'):
          self.assertEqual(repr(result_col_prop), repr(expected_col_prop))
        # `foreign_keys` is wrapped in a set for some reason for expected.
        # perhaps declarative_base removes it for result.
        elif prop == 'foreign_keys':
          self.assertEqual(set(result_col_prop), expected_col_prop)
        else:
          self.assertEqual(result_col_prop, expected_col_prop)



  def test_insert(self):
    Reservation = self.make_reservation()
    # insert
    reservation = Reservation(name='Me',
                              date=datetime.date(2015, 4, 2),
                              time=datetime.time(8, 25),
                              party=2)
    self.session.add(reservation)
    self.session.commit()

    reservations = self.session.query(Reservation).all()
    reservation_revs = self.session.query(Reservation.Revision).order_by('rev_created').all()
    # assert source 
    self.assertSeqEqual(
      reservations, 
      [ reservation ],
      pick=('id', 'created', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': 'Me',
          'date': datetime.date(2015, 4, 2),
          'time': datetime.time(8, 25),
          'party': 2,
          'rev_isdelete': False },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[0].rev_id)
    self.assertNotEqual(reservations[0].created, reservation_revs[0].rev_created)



  def test_update(self):
    Reservation = self.make_reservation()
    # insert
    reservation = Reservation(name='Me',
                              date=datetime.date(2015, 4, 13),
                              time=datetime.time(19, 00),
                              party=10)
    self.session.add(reservation)
    self.session.commit()
    # update
    reservation.date = datetime.date(2015, 4, 15)
    reservation.time = datetime.time(19, 30)
    reservation.party = 15
    self.session.commit()
    reservation.date = datetime.date(2015, 5, 15)
    reservation.time = datetime.time(19, 15)
    reservation.party = 11
    self.session.commit()

    reservations = self.session.query(Reservation).all()
    reservation_revs = self.session.query(Reservation.Revision).order_by('rev_created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': 'Me',
          'date': datetime.date(2015, 5, 15),
          'time': datetime.time(19, 15),
          'party': 11 },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': 'Me',
          'date': datetime.date(2015, 4, 13),
          'time': datetime.time(19, 00),
          'party': 10,
          'rev_isdelete': False },
        { 'id': reservation.id, 'created': reservation.created,
          'name': 'Me',
          'date': datetime.date(2015, 4, 15),
          'time': datetime.time(19, 30),
          'party': 15,
          'rev_isdelete': False },
        { 'id': reservation.id, 'created': reservation.created,
          'name': 'Me',
          'date': datetime.date(2015, 5, 15),
          'time': datetime.time(19, 15),
          'party': 11,
          'rev_isdelete': False },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[2].rev_id)
    self.assertCountUniqueValues(reservation_revs, 'rev_id', 3)
    self.assertNotEqual(reservations[0].created, reservation_revs[2].rev_created)
    self.assertCountUniqueValues(reservation_revs, 'rev_created', 3)



  def test_delete(self):
    Reservation = self.make_reservation()
    # insert
    reservation = Reservation(name='Me',
                              date=datetime.date(2015, 5, 21),
                              time=datetime.time(18, 45),
                              party=6)
    self.session.add(reservation)
    self.session.commit()    
    # delete
    self.session.delete(reservation)
    self.session.commit()

    reservation_revs = self.session.query(Reservation.Revision).order_by('rev_created').all()
    # assert source
    self.assertEqual(self.session.query(Reservation).all(), [])
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': 'Me',
          'date': datetime.date(2015, 5, 21),
          'time': datetime.time(18, 45), 'party': 6,
          'rev_isdelete': False },
        { 'id': reservation.id, 'created': None,
          'name': None,
          'date': None,
          'time': None,
          'party': None,
          'rev_isdelete': True },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids
    self.assertCountUniqueValues(reservation_revs, 'rev_id', 2)
    self.assertCountUniqueValues(reservation_revs, 'rev_created', 2)



  def test_insert_null(self):
    Reservation = self.make_reservation()
    # insert
    reservation = Reservation(name=None, date=None, time=None, party=None)
    self.session.add(reservation)
    self.session.commit()

    reservations = self.session.query(Reservation).all()
    reservation_revs = self.session.query(Reservation.Revision).order_by('rev_created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ reservation ],
      pick=('id', 'created', 'name', 'date', 'time', 'party'))
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': None, 'date': None, 'time': None, 'party': None,
          'rev_isdelete': False },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created time
    self.assertEqual(reservations[0].rev_id, reservation_revs[0].rev_id)
    self.assertNotEqual(reservations[0].created, reservation_revs[0].rev_created)



  def test_update_from_null(self):
    Reservation = self.make_reservation()
    # insert
    reservation = Reservation(name=None, date=None, time=None, party=None)
    self.session.add(reservation)
    self.session.commit()
    reservation.date = datetime.date(2015, 5, 15)
    reservation.time = datetime.time(19, 15)
    reservation.party = 11
    self.session.commit()

    reservations = self.session.query(Reservation).all()
    reservation_revs = self.session.query(Reservation.Revision).order_by('rev_created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': None,
          'date': datetime.date(2015, 5, 15),
          'time': datetime.time(19, 15),
          'party': 11 },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': None, 'date': None, 'time': None, 'party': None,
          'rev_isdelete': False },
        { 'id': reservation.id, 'created': reservation.created,
          'name': None,
          'date': datetime.date(2015, 5, 15),
          'time': datetime.time(19, 15),
          'party': 11,
          'rev_isdelete': False },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[1].rev_id)
    self.assertCountUniqueValues(reservation_revs, 'rev_id', 2)
    self.assertNotEqual(reservations[0].created, reservation_revs[1].rev_created)
    self.assertCountUniqueValues(reservation_revs, 'rev_created', 2)



  def test_update_to_null(self):
    Reservation = self.make_reservation()
    # insert
    reservation = Reservation(name=None,
                              date=datetime.date(2015, 5, 15),
                              time=datetime.time(19, 15),
                              party=11)
    self.session.add(reservation)
    self.session.commit()
    reservation.date = None
    reservation.time = None
    reservation.party = None
    self.session.commit()

    reservations = self.session.query(Reservation).all()
    reservation_revs = self.session.query(Reservation.Revision).order_by('rev_created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': None, 'date': None, 'time': None, 'party': None }
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': None,
          'date': datetime.date(2015, 5, 15),
          'time': datetime.time(19, 15),
          'party': 11,
          'rev_isdelete': False },
        { 'id': reservation.id, 'created': reservation.created,
          'name': None, 'date': None, 'time': None, 'party': None,
          'rev_isdelete': False },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created time
    self.assertEqual(reservations[0].rev_id, reservation_revs[1].rev_id)
    self.assertCountUniqueValues(reservation_revs, 'rev_id', 2)
    self.assertNotEqual(reservations[0].created, reservation_revs[1].rev_created)
    self.assertCountUniqueValues(reservation_revs, 'rev_created', 2)



  def test_record_on_flush_only(self):
    Reservation = self.make_reservation()
    # insert
    reservation = Reservation(name='Me', 
                              date=datetime.date(2015, 4, 13), 
                              time=datetime.time(19, 00), party=10)
    self.session.add(reservation)
    # update
    reservation.date = datetime.date(2015, 4, 15)
    reservation.time = datetime.time(19, 30)
    reservation.party = 15
    self.session.flush()
    reservation.date = datetime.date(2015, 5, 15)
    reservation.time = datetime.time(19, 15)
    reservation.party = 11
    self.session.delete(reservation)
    self.session.commit()

    # assert source
    self.assertEqual(self.session.query(Reservation).all(), [])   
    # assert revisions
    self.assertSeqEqual(
      self.session.query(Reservation.Revision).order_by('rev_created').all(),
      [ { 'id': reservation.id, 'created': reservation.created,
          'name': 'Me',
          'date': datetime.date(2015, 4, 15),
          'time': datetime.time(19, 30),
          'party': 15,
          'rev_isdelete': False },
        { 'id': reservation.id, 'created': None,
          'name': None, 'date': None, 'time': None, 'party': None,
          'rev_isdelete': True },
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )



  def test_relationship(self):
    class SomeClass(Versioned, self.Base):
      __tablename__ = 'someclass'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, default=time.time, nullable=False)
      name = sa.Column(sa.String)
      related_id = sa.Column(sa.Integer, sa.ForeignKey('somerelated.id'))
      related = sa.orm.relationship("SomeRelated", backref='classes')
      def __init__(self, *args, **kwargs):
        super(SomeClass, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())

    class SomeRelated(Versioned, self.Base):
      __tablename__ = 'somerelated'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, default=time.time, nullable=False)
      desc = sa.Column(sa.String)
      def __init__(self, *args, **kwargs):
        super(SomeRelated, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())

    SomeClass.broadcast_crud()
    SomeClassRev = SomeClass.Revision
    SomeRelated.broadcast_crud()
    SomeRelatedRev = SomeRelated.Revision
    self.create_tables()

    sess = self.session
    sc1 = SomeClass(name='sc1')
    sess.add(sc1)
    sess.commit()
    sr1 = SomeRelated(desc='sr1')
    sc1.related = sr1
    sess.commit()

    # assert source
    self.assertSeqEqual(
      self.session.query(SomeClass).all(),
      [sc1],
      pick=('id', 'name')
    )
    self.assertSeqEqual(
      self.session.query(SomeRelated).all(),
      [sr1],
      pick=('id', 'desc')
    )
    # assert revisions
    self.assertSeqEqual(
      sess.query(SomeClassRev).order_by(SomeClassRev.rev_created).all(),
      [
        { 'id': sc1.id, 'name': 'sc1', 'related_id': None },
        { 'id': sc1.id, 'name': 'sc1', 'related_id': sr1.id },
      ],
      pick=('id', 'name', 'related_id')
    )
    self.assertSeqEqual(
      sess.query(SomeRelatedRev).order_by(SomeRelatedRev.rev_created).all(),
      [
        { 'id': sr1.id, 'desc': 'sr1' },
      ],
      pick=('id', 'desc')
    )



  def test_backref_relationship(self):
    class SomeClass(Versioned, self.Base):
      __tablename__ = 'someclass'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, default=time.time, nullable=False)
      name = sa.Column(sa.String)
      def __init__(self, *args, **kwargs):
        super(SomeClass, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())

    class SomeRelated(Versioned, self.Base):
      __tablename__ = 'somerelated'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, default=time.time, nullable=False)
      desc = sa.Column(sa.String)
      related_id = sa.Column(sa.Integer, sa.ForeignKey('someclass.id'))
      related = sa.orm.relationship("SomeClass", backref='related')
      def __init__(self, *args, **kwargs):
        super(SomeRelated, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())

    SomeClass.broadcast_crud()
    SomeClassRev = SomeClass.Revision
    SomeRelated.broadcast_crud()
    SomeRelatedRev = SomeRelated.Revision
    self.create_tables()

    sess = self.session
    sc1 = SomeClass(name='sc1')
    sess.add(sc1)
    sess.commit()
    sr1 = SomeRelated(desc='sr1', related=sc1)
    sess.add(sr1)
    sess.commit()
    sr1.desc = 'sr2'
    sess.commit()
    sess.delete(sr1)
    sess.commit()

    # assert source
    self.assertSeqEqual(
      self.session.query(SomeClass).all(),
      [sc1],
      pick=('id', 'name')
    )
    self.assertSeqEqual(
      self.session.query(SomeRelated).all(),
      [],
      pick=('id', 'desc')
    )
    # assert revisions
    self.assertSeqEqual(
      sess.query(SomeClassRev).order_by(SomeClassRev.rev_created).all(),
      [
        { 'id': sc1.id, 'name': 'sc1' },
      ],
      pick=('id', 'name')
    )
    self.assertSeqEqual(
      sess.query(SomeRelatedRev).order_by(SomeRelatedRev.rev_created).all(),
      [
        { 'id': sr1.id, 'desc': 'sr1', 'related_id': sc1.id,
          'rev_isdelete': False },
        { 'id': sr1.id, 'desc': 'sr2', 'related_id': sc1.id,
          'rev_isdelete': False },
        { 'id': sr1.id, 'desc': None, 'related_id': None,
          'rev_isdelete': True },
      ],
      pick=('id', 'desc', 'rev_isdelete')
   )



  def test_association_object_rev_schema_creation(self):
    User, UserRev, Keyword, KeywordRev, UserKeyword, UserKeywordRev = self.make_user_keyword()

    result = UserKeywordRev.__table__
    expected = sa.Table(
      'uk_rev_prime', self.Base.metadata,
      sa.Column('rev_id', sa.String(length=36), primary_key=True),
      sa.Column('rev_created', sa.Float, nullable=False),
      sa.Column('rev_isdelete', sa.Boolean, default=False, nullable=False),
      sa.Column('user_id', sa.String, nullable=False),
      sa.Column('keyword_id', sa.String, nullable=False),
    )

    for col in ('rev_isdelete', 'rev_id', 'rev_created', 'user_id', 'keyword_id'):
      for prop in ('name', 'type', 'default', 'primary_key', 'nullable',
                   'foreign_keys'):
        result_col_prop = getattr(getattr(result.c, col), prop) 
        expected_col_prop = getattr(getattr(expected.c, col), prop)
        # todo: figure out these "hacks"
        # `type`, `default` are returned as a method, hence the repr to get it 
        # to compare
        if prop in ('type', 'default'):
          self.assertEqual(repr(result_col_prop), repr(expected_col_prop))
        # `foreign_keys` is wrapped in a set for some reason for expected.
        # perhaps declarative_base removes it for result.
        elif prop == 'foreign_keys':
          self.assertEqual(set(result_col_prop), expected_col_prop)
        else:
          self.assertEqual(result_col_prop, expected_col_prop)



  def test_association_object_insert(self):
    User, UserRev, Keyword, KeywordRev, UserKeyword, UserKeywordRev = self.make_user_keyword()

    sess = self.session
    boo = Keyword(word='boo')
    hoo = Keyword(word='hoo')
    steve = User(name='steve')
    allan = User(name='allan')
    sess.add(boo); sess.flush()
    sess.add(hoo); sess.flush()
    sess.add(steve); sess.flush()
    sess.add(allan); sess.flush()
    steve.keywords.append(boo); sess.flush()
    allan.keywords.append(hoo); sess.flush()
    sess.commit()

    # assert source
    self.assertSeqEqual(
      sess.query(User).all(),
      [steve, allan], 
      pick=('name')
    )
    self.assertSeqEqual(
      sess.query(Keyword).all(),
      [boo, hoo],
      pick=('word')
    )
    self.assertSeqEqual(
      sess.query(UserKeyword).all(),
      [ 
        { 'user_id': steve.id, 'keyword_id': boo.id },
        { 'user_id': allan.id, 'keyword_id': hoo.id },
      ],
      pick=('user_id', 'keyword_id')
    )
    # assert revisions
    self.assertSeqEqual(
      sess.query(UserRev).order_by(User.Revision.rev_created).all(),
      [
        { 'id': steve.id, 'name': 'steve', 'rev_isdelete': False  },
        { 'id': allan.id, 'name': 'allan', 'rev_isdelete': False  },
      ],
      pick=('id', 'name', 'rev_isdelete')
    )
    self.assertSeqEqual(
      sess.query(KeywordRev).order_by(KeywordRev.rev_created).all(),
      [
        { 'id': boo.id, 'word': 'boo', 'rev_isdelete': False },
        { 'id': hoo.id, 'word': 'hoo', 'rev_isdelete': False },
      ],
      pick=('id', 'word', 'rev_isdelete')
    )
    self.assertSeqEqual(
      sess.query(UserKeywordRev).order_by(UserKeywordRev.rev_created).all(),
      [
        { 'user_id': steve.id, 'keyword_id': boo.id, 'rev_isdelete': False },
        { 'user_id': allan.id, 'keyword_id': hoo.id, 'rev_isdelete': False },
      ],
      pick=('user_id', 'keyword_id', 'rev_isdelete')
    )



  def test_association_object_delete(self):
    User, UserRev, Keyword, KeywordRev, UserKeyword, UserKeywordRev = self.make_user_keyword()

    sess = self.session
    boo = Keyword(word='boo')
    steve = User(name='steve')
    sess.add(boo)
    sess.add(steve)
    steve.keywords.append(boo)
    sess.commit()
    steve.keywords.remove(boo)
    sess.commit()

    # assert source
    self.assertSeqEqual(
      sess.query(User).all(),
      [steve], 
      pick=('name')
    )
    self.assertSeqEqual(
      sess.query(Keyword).all(),
      [boo],
      pick=('word')
    )
    self.assertSeqEqual(
      sess.query(UserKeyword).all(),
      [],
      pick=('user_id', 'keyword_id')
    )
    # assert revisions
    self.assertSeqEqual(
      sess.query(UserRev).order_by(User.Revision.rev_created).all(),
      [
        { 'id': steve.id, 'name': 'steve', 'rev_isdelete': False },
      ],
      pick=('id', 'name', 'rev_isdelete')
    )
    self.assertSeqEqual(
      sess.query(KeywordRev).order_by(KeywordRev.rev_created).all(),
      [
        { 'id': boo.id, 'word': 'boo', 'rev_isdelete': False },
      ],
      pick=('id', 'word', 'rev_isdelete')
    )
    self.assertSeqEqual(
      sess.query(UserKeywordRev).order_by(UserKeywordRev.rev_created).all(),
      [
        { 'user_id': steve.id, 'keyword_id': boo.id, 'rev_isdelete': False },
        { 'user_id': steve.id, 'keyword_id': boo.id, 'rev_isdelete': True },
      ],
      pick=('user_id', 'keyword_id', 'rev_isdelete')
    )



  def test_association_object_delete_cascade(self):
    User, UserRev, Keyword, KeywordRev, UserKeyword, UserKeywordRev = self.make_user_keyword()

    sess = self.session
    boo = Keyword(word='boo')
    hoo = Keyword(word='hoo')
    steve = User(name='steve')
    allan = User(name='allan')
    sess.add(boo); sess.flush()
    sess.add(hoo); sess.flush()
    sess.add(steve); sess.flush()
    sess.add(allan); sess.flush()
    steve.keywords.append(boo); sess.flush()
    allan.keywords.append(hoo); sess.flush()
    sess.commit()
    sess.delete(boo)
    sess.commit()

    # assert source
    self.assertSeqEqual(
      sess.query(User).all(),
      [steve, allan], 
      pick=('name')
    )
    self.assertSeqEqual(
      sess.query(Keyword).all(),
      [hoo],
      pick=('word')
    )
    self.assertSeqEqual(
      sess.query(UserKeyword).all(),
      [ 
        { 'user_id': allan.id, 'keyword_id': hoo.id },
      ],
      pick=('user_id', 'keyword_id')
    )
    # assert revisions
    self.assertSeqEqual(
      sess.query(UserRev).order_by(User.Revision.rev_created).all(),
      [
        { 'id': steve.id, 'name': 'steve', 'rev_isdelete': False },
        { 'id': allan.id, 'name': 'allan', 'rev_isdelete': False },
      ],
      pick=('id', 'name', 'rev_isdelete')
    )
    self.assertSeqEqual(
      sess.query(KeywordRev).order_by(KeywordRev.rev_created).all(),
      [
        { 'id': boo.id, 'word': 'boo', 'rev_isdelete': False },
        { 'id': hoo.id, 'word': 'hoo', 'rev_isdelete': False },
        { 'id': boo.id, 'word': None, 'rev_isdelete': True },
      ],
      pick=('id', 'word', 'rev_isdelete')
    )
    self.assertSeqEqual(
      sess.query(UserKeywordRev).order_by(UserKeywordRev.rev_created).all(),
      [
        { 'user_id': steve.id, 'keyword_id': boo.id, 'rev_isdelete': False },
        { 'user_id': allan.id, 'keyword_id': hoo.id, 'rev_isdelete': False },
        { 'user_id': steve.id, 'keyword_id': boo.id, 'rev_isdelete': True },
      ],
      pick=('user_id', 'keyword_id', 'rev_isdelete')
    )



  def test_cannot_update_revision(self):
    Reservation = self.make_reservation()

    reservation = Reservation(name='Me',
                              date=datetime.date(2015, 4, 2),
                              time=datetime.time(8, 25),
                              party=2)
    self.session.add(reservation)
    self.session.commit()

    rev = self.session.query(Reservation.Revision).filter_by(id=reservation.id).one()
    rev.name = 'You'
    self.assertRaises(UpdateForbidden, self.session.commit)



  def test_cannot_delete_revison(self):
    Reservation = self.make_reservation()

    reservation = Reservation(name='Me',
                              date=datetime.date(2015, 4, 2),
                              time=datetime.time(8, 25),
                              party=2)
    self.session.add(reservation)
    self.session.commit()

    rev = self.session.query(Reservation.Revision).filter_by(id=reservation.id).one()
    self.session.delete(rev)
    self.assertRaises(DeleteForbidden, self.session.commit)
