# -*- coding: utf-8 -*-
import datetime
import time
import uuid

from sqlalchemy import Column, Date, DateTime, Integer, Float, String, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative.base import _declarative_constructor as SaInit
from sqlalchemy.orm import sessionmaker

from ..versioned import Versioned


Base = declarative_base()
Session = sessionmaker()


class Reservation(Versioned, Base):
  __tablename__ = 'reservations'
  id = Column(String, primary_key=True)
  created = Column(Float, nullable=False)
  name = Column(String)
  date = Column(Date)
  time = Column(Time)
  party = Column(Integer)

  def __init__(self, *args, **kwargs):
    self.id = str(uuid.uuid4())
    self.created = time.time()
    SaInit(self, *args, **kwargs)

  def __repr__(self):
    return '<Reservation(id="%s", rev_id="%s", created="%s", name="%s", date="%s", time="%s", party="%s">' % (self.id, self.rev_id, self.created, self.name, self.date, self.time, self.party)

Reservation.broadcast_crud()
