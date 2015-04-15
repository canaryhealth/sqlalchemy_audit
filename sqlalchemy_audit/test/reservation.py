# -*- coding: utf-8 -*-
import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()
Session = sessionmaker()


class Reservation(Base):
  __tablename__ = 'reservations'
  id = Column(Integer, primary_key=True)
  name = Column(String)
  date = Column(Date)
  time = Column(Time)
  party = Column(Integer)
  last_modified = Column(DateTime, nullable=False,
                         default=datetime.datetime.utcnow(), 
                         onupdate=datetime.datetime.utcnow())

  def __repr__(self):
    return '<Reservation(name="%s", date="%s", time="%s", party="%d">' % (self.name, self.date, self.time, self.party)
