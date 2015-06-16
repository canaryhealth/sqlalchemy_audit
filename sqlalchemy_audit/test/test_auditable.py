# -*- coding: utf-8 -*-
import datetime
import time
import unittest
import uuid

import sqlalchemy as sa
from canary.model.util import RestrictingForeignKey

from . import DbTestCase
from .reservation import Reservation, Base
from ..auditable import Auditable


class TestAuditable(DbTestCase):
  def list_comp(self, seq, attr):
    return [ getattr(x, 'rev_id') for x in seq ]



  def test_schema(self):
    raise unittest.SkipTest('TODO')
    class A(Auditable, Base):
      __tablename__ = 'a'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, nullable=False)
      name = sa.Column(sa.String, default='a', nullable=False)
      b_id = sa.Column(sa.String, RestrictingForeignKey('b.id'), nullable=False)

    class B(Base):
      __tablename__ = 'b'
      id = sa.Column(sa.String, primary_key=True)
      name = sa.Column(sa.String)

    A.broadcast_crud()
    self.create_tables()

    result = A.Revision.__table__
    expected = sa.Table(
      'a_rev_prime', Base.metadata,
      sa.Column('rev_isdelete', sa.Boolean, default=False, nullable=False),
      sa.Column('id', sa.String, nullable=True),
      sa.Column('rev_id', sa.String, primary_key=True),
      sa.Column('created', sa.Float, nullable=True),
      sa.Column('name', sa.String, default=None, nullable=True),
      sa.Column('b_id', sa.String, nullable=True)
    )

    for col in ('rev_isdelete', 'id', 'rev_id', 'created', 'name', 'b_id'):
      for prop in ('name', 'type', 'default', 'primary_key', 'nullable', 
                   'foreign_keys'):
        pass
        # todo: how do i compare their values...
        # print col + '.' + prop
        # print getattr(getattr(result.c, col), prop) 
        # print getattr(getattr(expected.c, col), prop)
        # print '----------'

     #import pdb; pdb.set_trace()



  def test_insert(self):
    # insert
    reservation = Reservation(name='Me', 
                              date=datetime.date(2015, 4, 2), 
                              time=datetime.time(8, 25), party=2)
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
      [ Reservation.Revision(id=reservation.id,  created=reservation.created,
                       name='Me',
                       date=datetime.date(2015, 4, 2),
                       time=datetime.time(8, 25),
                       party=2, rev_isdelete=False),
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[0].rev_id)
    self.assertNotEqual(reservations[0].created, reservation_revs[0].rev_created)



  def test_update(self):
    # insert
    reservation = Reservation(name='Me', 
                              date=datetime.date(2015, 4, 13), 
                              time=datetime.time(19, 00), party=10)
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
      [ Reservation(id=reservation.id, created=reservation.created,
                    name='Me',
                    date=datetime.date(2015, 5, 15), 
                    time=datetime.time(19, 15),
                    party=11),
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ Reservation.Revision(id=reservation.id, created=reservation.created,
                             name='Me',
                             date=datetime.date(2015, 4, 13), 
                             time=datetime.time(19, 00),
                             party=10, rev_isdelete=False),
        Reservation.Revision(id=reservation.id, created=reservation.created,
                             name='Me',
                             date=datetime.date(2015, 4, 15),
                             time=datetime.time(19, 30),
                             party=15, rev_isdelete=False),
        Reservation.Revision(id=reservation.id, created=reservation.created,
                             name='Me',
                             date=datetime.date(2015, 5, 15),
                             time=datetime.time(19, 15),
                             party=11, rev_isdelete=False),
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[2].rev_id)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_id'))), 3)
    self.assertNotEqual(reservations[0].created, reservation_revs[2].rev_created)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_created'))), 3)



  def test_delete(self):
    # insert
    reservation = Reservation(name='Me', 
                              date=datetime.date(2015, 5, 21), 
                              time=datetime.time(18, 45), party=6)
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
      [ Reservation.Revision(id=reservation.id, created=reservation.created,
                             name='Me',
                             date=datetime.date(2015, 5, 21), 
                             time=datetime.time(18, 45),
                             party=6, rev_isdelete=False),
        Reservation.Revision(id=reservation.id, created=None,
                             name=None,
                             date=None, time=None, 
                             party=None, rev_isdelete=True),
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_id'))), 2)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_created'))), 2)



  def test_insert_null(self):
    # insert
    reservation = Reservation(name=None, 
                              date=None, time=None, party=None)
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
      [ Reservation.Revision(id=reservation.id, created=reservation.created,
                             name=None,
                             date=None, time=None, party=None,
                             rev_isdelete=False),
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created time
    self.assertEqual(reservations[0].rev_id, reservation_revs[0].rev_id)
    self.assertNotEqual(reservations[0].created, reservation_revs[0].rev_created)



  def test_update_from_null(self):
    # insert
    reservation = Reservation(name=None, 
                              date=None, time=None, party=None)
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
      [ Reservation(id=reservation.id, created=reservation.created,
                    name=None,
                    date=datetime.date(2015, 5, 15), 
                    time=datetime.time(19, 15),
                    party=11)
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ Reservation.Revision(id=reservation.id, created=reservation.created,
                             name=None, 
                             date=None, time=None, party=None,
                             rev_isdelete=False),
        Reservation.Revision(id=reservation.id, created=reservation.created,
                             name=None,
                             date=datetime.date(2015, 5, 15),
                             time=datetime.time(19, 15),
                             party=11, rev_isdelete=False),
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[1].rev_id)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_id'))), 2)
    self.assertNotEqual(reservations[0].created, reservation_revs[1].rev_created)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_created'))), 2)



  def test_update_to_null(self):
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
      [ Reservation(id=reservation.id, created=reservation.created,
                    name=None,
                    date=None, time=None, party=None)
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ Reservation.Revision(id=reservation.id, created=reservation.created,
                             name=None,
                             date=datetime.date(2015, 5, 15),
                             time=datetime.time(19, 15),
                             party=11, rev_isdelete=False),
        Reservation.Revision(id=reservation.id, created=reservation.created,
                             name=None, 
                             date=None, time=None, party=None,
                             rev_isdelete=False),
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )
    # assert rev ids and created time
    self.assertEqual(reservations[0].rev_id, reservation_revs[1].rev_id)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_id'))), 2)
    self.assertNotEqual(reservations[0].created, reservation_revs[1].rev_created)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_created'))), 2)



  def test_flushes(self):
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
      [ Reservation.Revision(id=reservation.id, created=reservation.created,
                             name='Me',
                             date=datetime.date(2015, 4, 15),
                             time=datetime.time(19, 30),
                             party=15, rev_isdelete=False),
        Reservation.Revision(id=reservation.id, created=None,
                             name=None,
                             date=None, time=None, 
                             party=None, rev_isdelete=True),
      ],
      pick=('id', 'created', 'name', 'date', 'time', 'party', 'rev_isdelete')
    )



  def test_relationship(self):
    class SomeClass(Auditable, Base):
      __tablename__ = 'someclass'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, default=time.time, nullable=False)
      name = sa.Column(sa.String)
      related_id = sa.Column(sa.Integer, sa.ForeignKey('somerelated.id'))
      related = sa.orm.relationship("SomeRelated", backref='classes')
      def __init__(self, *args, **kwargs):
        super(SomeClass, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())

    class SomeRelated(Auditable, Base):
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
      sess.query(SomeClassRev).order_by(SomeClassRev.created).all(),
      [
        SomeClassRev(id=sc1.id, name='sc1', related_id=None),
        SomeClassRev(id=sc1.id, name='sc1', related_id=sr1.id),
      ],
      pick=('id', 'name', 'related_id')
    )
    self.assertSeqEqual(
      sess.query(SomeRelatedRev).order_by(SomeRelatedRev.created).all(),
      [
        SomeRelatedRev(id=sr1.id, desc='sr1')
      ],
      pick=('id', 'desc')
    )



  def test_backref_relationship(self):
    raise unittest.SkipTest('unpollute Base.metadata')
    class SomeClass(Auditable, Base):
      __tablename__ = 'someclass'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float, default=time.time, nullable=False)
      name = sa.Column(sa.String)
      def __init__(self, *args, **kwargs):
        super(SomeClass, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())

    class SomeRelated(Auditable, Base):
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
      sess.query(SomeClassRev).order_by(SomeClassRev.created).all(),
      [
        # todo: there are two b/c the relationship assignment does not
        #       consider whether the fields were changed.
        SomeClassRev(id=sc1.id, name='sc1'),
        SomeClassRev(id=sc1.id, name='sc1'),
      ],
      pick=('id', 'name')
    )
    self.assertSeqEqual(
      sess.query(SomeRelatedRev).order_by(SomeRelatedRev.created).all(),
      [
        SomeRelatedRev(id=sr1.id, desc='sr1', related_id=sc1.id,
                       rev_isdelete=False),
        SomeRelatedRev(id=sr1.id, desc='sr2', related_id=sc1.id,
                       rev_isdelete=False),
        SomeRelatedRev(id=sr1.id, desc=None, related_id=None,
                       rev_isdelete=True),
      ],
      pick=('id', 'desc', 'rev_isdelete')
    )



  def test_association_object(self):
    raise unittest.SkipTest('TODO: get association object to work')
    class User(Auditable, Base):
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

    class Keyword(Auditable, Base):
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

    class UserKeyword(Auditable, Base):
      __tablename__ = 'user_keyword'
      id = sa.Column(sa.String, primary_key=True)
      created = sa.Column(sa.Float)
      user_id = sa.Column(sa.String, sa.ForeignKey('user.id'),
                          primary_key=True)
      user = sa.orm.relationship(
        'User', 
        backref=sa.orm.backref('user_keyword', cascade='all, delete-orphan'))
      keyword_id = sa.Column(sa.Integer, sa.ForeignKey('keyword.id'),
                             primary_key=True)
      keyword = sa.orm.relationship(
        'Keyword',
        backref=sa.orm.backref('user_keyword', cascade='all, delete-orphan'))
      def __init__(self, *args, **kwargs):
        super(UserKeyword, self).__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())
        self.created = time.time()

    User.broadcast_crud()
    UserRev = User.Revision
    Keyword.broadcast_crud()
    KeywordRev = Keyword.Revision
    UserKeyword.broadcast_crud()
    UserKeywordRev = UserKeyword.Revision
    self.create_tables()
    sess = self.session

    # part a
    boo = Keyword(word='boo')
    hoo = Keyword(word='hoo')
    steve = User(name='steve')
    allan = User(name='allan')
    sess.add(boo)
    sess.add(hoo)
    sess.add(steve)
    sess.add(allan)
    steve.keywords.append(boo)
    steve.keywords.append(hoo)
    allan.keywords.append(hoo)
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
      # todo: need to figure out how to create UserKeyword obj from ids, work around by
      #       querying for it
      [ 
        sess.query(UserKeyword).filter(UserKeyword.user_id==steve.id, UserKeyword.keyword_id==boo.id).one(),
        sess.query(UserKeyword).filter(UserKeyword.user_id==steve.id, UserKeyword.keyword_id==hoo.id).one(),
        sess.query(UserKeyword).filter(UserKeyword.user_id==allan.id, UserKeyword.keyword_id==hoo.id).one(),
      ],
      pick=('user_id', 'keyword_id')
    )
    # assert revisions
    user_rev_a = [
      UserRev(id=steve.id, name='steve'),
      UserRev(id=allan.id, name='allan'),
    ]
    kw_rev_a = [
      KeywordRev(id=boo.id, word='boo'),
      KeywordRev(id=hoo.id, word='hoo'),
    ]
    user_kw_rev_a = [
      # todo
      #steve boo
      #steve hoo
      #allan hoo
    ]
    self.assertSeqEqual(
      sess.query(UserRev).order_by(UserRev.created).all(),
      user_rev_a,
      pick=('id', 'name')
    )
    self.assertSeqEqual(
      sess.query(KeywordRev).order_by(KeywordRev.created).all(),
      kw_rev_a,
      pick=('id', 'word')
    )
    # todo: assert assoc


    # part b
    allan.keywords.remove(hoo)
    sess.commit()

    user_rev_b = [
      UserRev(id=allan.id, name='allan'),
    ]
    user_kw_rev_b = [
      # delete allan hoo
    ]
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
    # todo: assert assoc
    self.assertSeqEqual(
      sess.query(UserKeyword).all(),
      # todo: need to figure out how to create UserKeyword obj from ids, work around by
      #       querying for it
      [ 
        sess.query(UserKeyword).filter(UserKeyword.user_id==steve.id, UserKeyword.keyword_id==boo.id).one(),
        sess.query(UserKeyword).filter(UserKeyword.user_id==steve.id, UserKeyword.keyword_id==hoo.id).one(),
      ],
      pick=('user_id', 'keyword_id')
    )
    # assert revisions
    self.assertSeqEqual(
      sess.query(UserRev).order_by(UserRev.created).all(),
      user_rev_a + user_rev_b,
      pick=('id', 'name')
    )
    self.assertSeqEqual(
      sess.query(KeywordRev).order_by(KeywordRev.created).all(),
      kw_rev_a,
      pick=('id', 'word')
    )
    # todo: assert assoc


    # part c
    sess.delete(hoo)
    sess.commit()

    # assert source
    self.assertSeqEqual(
      sess.query(User).all(),
      [steve, allan], 
      pick=('name')
    )
    self.assertSeqEqual(
      sess.query(Keyword).all(),
      [boo],
      pick=('word')
    )
    # todo: assert assoc
    self.assertSeqEqual(
      sess.query(UserKeyword).all(),
      # todo: need to figure out how to create UserKeyword obj from ids, work around by
      #       querying for it
      [ 
        sess.query(UserKeyword).filter(UserKeyword.user_id==steve.id, UserKeyword.keyword_id==boo.id).one(),
      ],
      pick=('user_id', 'keyword_id')
    )

    kw_rev_c = [
      # delete hoo
    ]
    user_kw_rev_c = [
      # delete steve hoo
    ]
