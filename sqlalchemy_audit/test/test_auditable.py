# -*- coding: utf-8 -*-
import datetime
import uuid

from . import DbTestCase
from .reservation import Reservation


class TestAuditable(DbTestCase):

  def test_insert(self):
    # insert
    reservation = Reservation(id=str(uuid.uuid4()), name='Me', 
                              date=datetime.date(2015, 4, 2), 
                              time=datetime.time(8, 25), party=2)
    self.session.add(reservation)
    self.session.commit()


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
