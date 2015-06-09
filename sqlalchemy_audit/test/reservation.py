# -*- coding: utf-8 -*-
import datetime
import time
import uuid

from sqlalchemy import Column, Date, DateTime, Integer, Float, String, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative.base import _declarative_constructor as SaInit
from sqlalchemy.orm import sessionmaker

from ..auditable import Auditable


Base = declarative_base()
Session = sessionmaker()


class Reservation(Auditable, Base):
  __tablename__ = 'reservations'
  id = Column(String, primary_key=True)
  rev_id = Column(String, nullable=False)
  created = Column(Float, nullable=False)
  name = Column(String)
  date = Column(Date)
  time = Column(Time)
  party = Column(Integer)

  def __init__(self, *args, **kwargs):
    self.id = str(uuid.uuid4())
    self.rev_id = str(uuid.uuid4())
    self.created = time.time()
    SaInit(self, *args, **kwargs)

  def __repr__(self):
    return '<Reservation(id="%s", rev_id="%s", created="%s", name="%s", date="%s", time="%s", party="%s">' % (self.id, self.rev_id, self.created, self.name, self.date, self.time, self.party)

Reservation.broadcast_crud()
