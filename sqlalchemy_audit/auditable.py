# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# auth: Steve Yeung <steve@canary.md>
# date: 2015/06/04
# copy: (C) Copyright 2014-EOT Canary Health, Inc., All Rights Reserved.
#------------------------------------------------------------------------------
import aadict
import time
import uuid

import sqlalchemy as sa

class Auditable(object):
  '''
  Mixin that broadcasts and listens for DB CRUD operations and records the
  transaction as a new revision in a separate table.

  Usage
  -----
    # Set up DBSession
    DBSession = ...
    Auditable.auditable_session(DBSession)

    # Class inherits Auditable and broadcast CRUD events
    class MyClass(Auditable):
      ...

    MyClass.broadcast_crud()  
  '''
  DBSession = None

  # todo: switch to pub/sub or message broker instead of directly setting 
  #       the handler
  @staticmethod
  def before_insert(mapper, connection, target):
    Auditable.before_db_change(mapper, connection, target, 'insert')

  @staticmethod
  def before_update(mapper, connection, target):
    Auditable.before_db_change(mapper, connection, target, 'update')

  @staticmethod
  def before_delete(mapper, connection, target):
    Auditable.before_db_change(mapper, connection, target, 'delete')

  @staticmethod
  def before_db_change(mapper, connection, target, action):
    # re-roll the rev_id on change
    if action is not 'insert':
      target.rev_id = str(uuid.uuid4())

  
  @staticmethod
  def after_insert(mapper, connection, target):
    Auditable.after_db_change(mapper, connection, target, 'insert')

  @staticmethod
  def after_update(mapper, connection, target):
    Auditable.after_db_change(mapper, connection, target, 'update')

  @staticmethod
  def after_delete(mapper, connection, target):
    Auditable.after_db_change(mapper, connection, target, 'delete')

  @staticmethod
  def after_db_change(mapper, connection, target, action):
    # todo: should we handle the defaults in a constructor?
    attr = aadict.aadict()
    attr.isdelete = False
    attr.id = getattr(target, 'id')
    attr.rev_id = getattr(target, 'rev_id')
    attr.created = time.time()

    if action == 'delete':
      attr.isdelete = True
      # skips copying the rest of the fields (hence None)
    else:
      # todo: is there a better way to copy this?
      for c in target.__table__.c:
        if c.name not in ('id', 'rev_id', 'created'):  # already assigned
          attr[c.name] = getattr(target, c.name)
    rev = target.__rev_class__(**attr)
    Auditable.DBSession.add(rev)


  @classmethod
  def broadcast_crud(cls):
    # todo: add rev_id to cls automatically

    # create revision class
    Auditable.create_rev_class(cls)

    # register listeners
    sa.event.listen(cls, 'before_insert', cls.before_insert)
    sa.event.listen(cls, 'before_update', cls.before_update)
    sa.event.listen(cls, 'before_delete', cls.before_delete)
    sa.event.listen(cls, 'after_insert', cls.after_insert)
    sa.event.listen(cls, 'after_update', cls. after_update)
    sa.event.listen(cls, 'after_delete', cls.after_delete)


  @staticmethod
  def create_rev_class(cls):
    def _col_copy(col):
      ''''
      Copies column and removes nullable, constraints, and defaults. 
      '''
      col = col.copy()
      col.nullable = True
      col.unique = False
      col.primary_key = False
      col.foreign_keys = []
      col.default = col.server_default = None
      # todo: feels a bit hard-coded
      if col.name == 'rev_id':
        col.primary_key = True
      return col

    properties = sa.util.OrderedDict()
    rev_cols = []
    rev_cols.append(
      sa.Column('isdelete', sa.Boolean, default=False, nullable=False))
    for column in cls.__mapper__.local_table.c:
      rev_cols.append(_col_copy(column))

    table = sa.Table(
      cls.__mapper__.local_table.name + '_rev',
      cls.__mapper__.local_table.metadata,
      *rev_cols,
      schema=cls.__mapper__.local_table.schema
    )
    bases = cls.__mapper__.base_mapper.class_.__bases__
    rev_cls = type.__new__(type, "%sRev" % cls.__name__, bases, {})  
    mapper = sa.orm.mapper(
      rev_cls,
      table,
      properties=properties
    )
    rev_cls.__table__ = table
    rev_cls.__mapper__ = mapper
    cls.__rev_class__ = rev_cls

  @classmethod
  def auditable_session(cls, session):
    cls.DBSession = session

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
