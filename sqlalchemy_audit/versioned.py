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

class Versioned(object):
  '''
  Mixin that broadcasts and listens for DB CRUD operations and records the
  transaction as a new revision in a separate table.

  Usage
  -----
    # Set up DBSession
    DBSession = ...
    Versioned.versioned_session(DBSession)

    # Class inherits Versioned and broadcast CRUD events
    class MyClass(Versioned):
      ...

    MyClass.broadcast_crud()
  '''
  DBSession = None

  rev_id = sa.Column('rev_id', sa.String(36), nullable=False)

  # todo: switch to pub/sub or message broker instead of directly setting 
  #       the handler
  @staticmethod
  def before_insert(mapper, connection, target):
    Versioned.before_db_change(mapper, connection, target, 'insert')

  @staticmethod
  def before_update(mapper, connection, target):
    Versioned.before_db_change(mapper, connection, target, 'update')

  @staticmethod
  def before_delete(mapper, connection, target):
    Versioned.before_db_change(mapper, connection, target, 'delete')

  @staticmethod
  def before_db_change(mapper, connection, target, action):
    # re-roll the rev_id on change
    # this is needed for insert b/c we don't have init to populate its value
    target.rev_id = str(uuid.uuid4())

  
  @staticmethod
  def after_insert(mapper, connection, target):
    Versioned.after_db_change(mapper, connection, target, 'insert')

  @staticmethod
  def after_update(mapper, connection, target):
    Versioned.after_db_change(mapper, connection, target, 'update')

  @staticmethod
  def after_delete(mapper, connection, target):
    Versioned.after_db_change(mapper, connection, target, 'delete')

  @staticmethod
  def after_db_change(mapper, connection, target, action):
    # todo: should we handle the defaults in a constructor?
    attr = aadict.aadict()
    attr.rev_id = getattr(target, 'rev_id')
    attr.rev_created = time.time()
    attr.rev_isdelete = False
    for k in target.__table__.primary_key:
      attr[k.name] = getattr(target, k.name)

    if action == 'delete':
      attr.rev_isdelete = True
      # skips copying the rest of the fields (hence None)
    else:
      # todo: is there a better way to copy this?
      for c in target.__table__.c:
        # skip primary key and namespaced fields (already assigned)
        if not (c.name.startswith('rev_') or c.primary_key is True):
          attr[c.name] = getattr(target, c.name)
    rev = target.Revision(**attr)
    Versioned.DBSession.add(rev)


  @classmethod
  def broadcast_crud(cls):
    # create revision class
    Versioned.create_rev_class(cls)

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
      if col.primary_key is True:
        col.nullable = False
      else:
        col.nullable = True
      col.unique = False
      col.primary_key = False
      col.foreign_keys = []
      col.default = col.server_default = None
      return col

    properties = sa.util.OrderedDict()
    rev_cols = []
    rev_cols.append(
      sa.Column('rev_id', sa.String(36), nullable=False, primary_key=True))
    rev_cols.append(
      sa.Column('rev_created', sa.Float, nullable=False))
    rev_cols.append(
      sa.Column('rev_isdelete', sa.Boolean, nullable=False, default=False))
    for column in cls.__mapper__.local_table.c:
      # todo: ideally check to see if there are conflicts with the namespaced
      #       cols
      if not column.name.startswith('rev_'):
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
    cls.Revision = rev_cls

  @classmethod
  def versioned_session(cls, session):
    cls.DBSession = session

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------
