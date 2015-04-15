# -*- coding: utf-8 -*-
import unittest

from sqlalchemy import create_engine

from .reservation import Base, Session


class DbTestCase(unittest.TestCase):
  engine = create_engine('sqlite:///test.db', echo=True)

  def setUp(self):
    super(DbTestCase, self).setUp()
    Base.metadata.create_all(self.engine)
    Session.configure(bind=self.engine)
    self.session = Session()


  def tearDown(self):
    super(DbTestCase, self).tearDown()
    Base.metadata.drop_all(self.engine)