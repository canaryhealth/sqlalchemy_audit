# -*- coding: utf-8 -*-
import datetime
import uuid

from sqlalchemy import Column, Date, DateTime, Integer, String, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative.base import _declarative_constructor as SaInit
from sqlalchemy.orm import sessionmaker

from ..history_meta import Auditable


Base = declarative_base()
Session = sessionmaker()


class Reservation(Auditable, Base):
  __tablename__ = 'reservations'
  id = Column(String, primary_key=True)
  name = Column(String)
  date = Column(Date)
  time = Column(Time)
  party = Column(Integer)

  def __init__(self, *args, **kwargs):
    self.id = str(uuid.uuid4())
    SaInit(self, *args, **kwargs)

  def __repr__(self):
    return '<Reservation(id="%s", name="%s", date="%s", time="%s", party="%s">' % (self.id, self.name, self.date, self.time, self.party)
