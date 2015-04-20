# -*- coding: utf-8 -*-
import datetime
import morph
import uuid

from . import DbTestCase
from .reservation import Reservation


ReservationAudit = Reservation.__audit_mapper__.class_

class TestAuditable(DbTestCase):

  def assertSeqEqual(self, result, expected, pick=None):
    if pick is not None and morph.isseq(result) and morph.isseq(expected):
      result = [morph.pick(item, *morph.tolist(pick)) for item in result]
      expected = [morph.pick(item, *morph.tolist(pick)) for item in expected]

    self.assertEqual(result, expected, 'the lists are different')


  def test_insert(self):
    # insert
    reservation = Reservation(id=str(uuid.uuid4()), name='Me', 
                              date=datetime.date(2015, 4, 2), 
                              time=datetime.time(8, 25), party=2)
    self.session.add(reservation)
    self.session.commit()

    # assert source
    self.assertSeqEqual(
      self.session.query(Reservation).all(),
      [reservation],
      pick=('id', 'name', 'date', 'time', 'party'))

    # assert audit records
    self.assertSeqEqual(
      self.session.query(ReservationAudit).order_by('audit_timestamp').all(),
      [ ReservationAudit(id=reservation.id,  name='Me',
                         date=datetime.date(2015, 4, 2),
                         time=datetime.time(8, 25),
                         party=2, audit_isdelete=False),
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'audit_isdelete')
    )


  def test_update(self):
    # insert
    reservation = Reservation(id=str(uuid.uuid4()), name='Me', 
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

    # assert source
    self.assertSeqEqual(
      self.session.query(Reservation).all(),
      [ Reservation(id=reservation.id, name='Me',
                    date=datetime.date(2015, 5, 15), 
                    time=datetime.time(19, 15),
                    party=11)
      ],
      pick=('id', 'name', 'date', 'time', 'party')
    )
    
    # assert audit records
    self.assertSeqEqual(
      self.session.query(ReservationAudit).order_by('audit_timestamp').all(),
      [ ReservationAudit(id=reservation.id, name='Me',
                         date=datetime.date(2015, 4, 13), 
                         time=datetime.time(19, 00),
                         party=10, audit_isdelete=False),
        ReservationAudit(id=reservation.id, name='Me',
                         date=datetime.date(2015, 4, 15),
                         time=datetime.time(19, 30),
                         party=15, audit_isdelete=False),
        ReservationAudit(id=reservation.id, name='Me',
                         date=datetime.date(2015, 5, 15),
                         time=datetime.time(19, 15),
                         party=11, audit_isdelete=False),
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'audit_isdelete')
    )


  def test_delete(self):
    # insert
    reservation = Reservation(id=str(uuid.uuid4()), name='Me', 
                              date=datetime.date(2015, 5, 21), 
                              time=datetime.time(18, 45), party=6)
    self.session.add(reservation)
    self.session.commit()    
    # delete
    self.session.delete(reservation)
    self.session.commit()

    # assert source
    self.assertEqual(self.session.query(Reservation).all(), [])

    # assert audit records
    self.assertSeqEqual(
      self.session.query(ReservationAudit).order_by('audit_timestamp').all(),
      [ ReservationAudit(id=reservation.id, name='Me',
                         date=datetime.date(2015, 5, 21), 
                         time=datetime.time(18, 45),
                         party=6, audit_isdelete=False),
        ReservationAudit(id=reservation.id, name=None,
                         date=None, time=None, 
                         party=None, audit_isdelete=True),
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'audit_isdelete')
    )
