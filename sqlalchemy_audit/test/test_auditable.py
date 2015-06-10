# -*- coding: utf-8 -*-
import datetime

from . import DbTestCase
from .reservation import Reservation

ReservationAudit = Reservation.__rev_class__


class TestAuditable(DbTestCase):
  def list_comp(self, seq, attr):
    return [ getattr(x, 'rev_id') for x in seq ]



  def test_insert(self):
    # insert
    reservation = Reservation(name='Me', 
                              date=datetime.date(2015, 4, 2), 
                              time=datetime.time(8, 25), party=2)
    self.session.add(reservation)
    self.session.commit()

    reservations = self.session.query(Reservation).all()
    reservation_revs = self.session.query(ReservationAudit).order_by('created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ reservation ],
      pick=('id', 'name', 'date', 'time', 'party'))
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ ReservationAudit(id=reservation.id,  name='Me',
                         date=datetime.date(2015, 4, 2),
                         time=datetime.time(8, 25),
                         party=2, isdelete=False),
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[0].rev_id)
    self.assertNotEqual(reservations[0].created, reservation_revs[0].created)



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
    reservation_revs = self.session.query(ReservationAudit).order_by('created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ Reservation(id=reservation.id, name='Me',
                    date=datetime.date(2015, 5, 15), 
                    time=datetime.time(19, 15),
                    party=11),
      ],
      pick=('id', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ ReservationAudit(id=reservation.id, name='Me',
                         date=datetime.date(2015, 4, 13), 
                         time=datetime.time(19, 00),
                         party=10, isdelete=False),
        ReservationAudit(id=reservation.id, name='Me',
                         date=datetime.date(2015, 4, 15),
                         time=datetime.time(19, 30),
                         party=15, isdelete=False),
        ReservationAudit(id=reservation.id, name='Me',
                         date=datetime.date(2015, 5, 15),
                         time=datetime.time(19, 15),
                         party=11, isdelete=False),
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[2].rev_id)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_id'))), 3)
    self.assertNotEqual(reservations[0].created, reservation_revs[2].created)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'created'))), 3)



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

    reservation_revs = self.session.query(ReservationAudit).order_by('created').all()
    # assert source
    self.assertEqual(self.session.query(Reservation).all(), [])
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ ReservationAudit(id=reservation.id, name='Me',
                         date=datetime.date(2015, 5, 21), 
                         time=datetime.time(18, 45),
                         party=6, isdelete=False),
        ReservationAudit(id=reservation.id, name=None,
                         date=None, time=None, 
                         party=None, isdelete=True),
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'isdelete')
    )
    # assert rev ids
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_id'))), 2)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'created'))), 2)



  def test_insert_null(self):
    # insert
    reservation = Reservation(name=None, 
                              date=None, time=None, party=None)
    self.session.add(reservation)
    self.session.commit()

    reservations = self.session.query(Reservation).all()
    reservation_revs = self.session.query(ReservationAudit).order_by('created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ reservation ],
      pick=('id', 'name', 'date', 'time', 'party'))
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ ReservationAudit(id=reservation.id,  name=None,
                         date=None, time=None, party=None,
                         isdelete=False),
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'isdelete')
    )
    # assert rev ids and created time
    self.assertEqual(reservations[0].rev_id, reservation_revs[0].rev_id)
    self.assertNotEqual(reservations[0].created, reservation_revs[0].created)



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
    reservation_revs = self.session.query(ReservationAudit).order_by('created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ Reservation(id=reservation.id, name=None,
                    date=datetime.date(2015, 5, 15), 
                    time=datetime.time(19, 15),
                    party=11)
      ],
      pick=('id', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ ReservationAudit(id=reservation.id, name=None, 
                         date=None, time=None, party=None,
                         isdelete=False),
        ReservationAudit(id=reservation.id, name=None,
                         date=datetime.date(2015, 5, 15),
                         time=datetime.time(19, 15),
                         party=11, isdelete=False),
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'isdelete')
    )
    # assert rev ids and created times
    self.assertEqual(reservations[0].rev_id, reservation_revs[1].rev_id)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_id'))), 2)
    self.assertNotEqual(reservations[0].created, reservation_revs[1].created)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'created'))), 2)



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
    reservation_revs = self.session.query(ReservationAudit).order_by('created').all()
    # assert source
    self.assertSeqEqual(
      reservations,
      [ Reservation(id=reservation.id, name=None,
                    date=None, time=None, party=None)
      ],
      pick=('id', 'name', 'date', 'time', 'party')
    )
    # assert revisions
    self.assertSeqEqual(
      reservation_revs,
      [ ReservationAudit(id=reservation.id, name=None,
                         date=datetime.date(2015, 5, 15),
                         time=datetime.time(19, 15),
                         party=11, isdelete=False),
        ReservationAudit(id=reservation.id, name=None, 
                         date=None, time=None, party=None,
                         isdelete=False),
        
      ],
      pick=('id', 'name', 'date', 'time', 'party', 'isdelete')
    )
    # assert rev ids and created time
    self.assertEqual(reservations[0].rev_id, reservation_revs[1].rev_id)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'rev_id'))), 2)
    self.assertNotEqual(reservations[0].created, reservation_revs[1].created)
    self.assertEqual(len(set(self.list_comp(reservation_revs, 'created'))), 2)



  # def test_flushes(self):
  #   # insert
  #   reservation = Reservation(name='Me', 
  #                             date=datetime.date(2015, 4, 13), 
  #                             time=datetime.time(19, 00), party=10)
  #   self.session.add(reservation)
  #   self.session.flush()
  #   # update
  #   reservation.date = datetime.date(2015, 4, 15)
  #   reservation.time = datetime.time(19, 30)
  #   reservation.party = 15
  #   self.session.flush()
  #   reservation.date = datetime.date(2015, 5, 15)
  #   reservation.time = datetime.time(19, 15)
  #   reservation.party = 11
  #   self.session.flush()
  #   self.session.commit()

  #   # assert source
  #   self.assertSeqEqual(
  #     self.session.query(Reservation).all(),
  #     [ Reservation(id=reservation.id, name='Me',
  #                   date=datetime.date(2015, 5, 15), 
  #                   time=datetime.time(19, 15),
  #                   party=11)
  #     ],
  #     pick=('id', 'name', 'date', 'time', 'party')
  #   )
    
  #   # assert revisions
  #   self.assertSeqEqual(
  #     self.session.query(ReservationAudit).order_by('created').all(),
  #     [ ReservationAudit(id=reservation.id, name='Me',
  #                        date=datetime.date(2015, 4, 13), 
  #                        time=datetime.time(19, 00),
  #                        party=10, isdelete=False),
  #       ReservationAudit(id=reservation.id, name='Me',
  #                        date=datetime.date(2015, 4, 15),
  #                        time=datetime.time(19, 30),
  #                        party=15, isdelete=False),
  #       ReservationAudit(id=reservation.id, name='Me',
  #                        date=datetime.date(2015, 5, 15),
  #                        time=datetime.time(19, 15),
  #                        party=11, isdelete=False),
  #     ],
  #     pick=('id', 'name', 'date', 'time', 'party', 'isdelete')
  #   )
