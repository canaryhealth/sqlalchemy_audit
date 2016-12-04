# -*- coding: utf-8 -*-
import time
import uuid

import aadict
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

  rev_id = sa.Column('rev_id', sa.String(36), nullable=False, unique=True)

  # todo: switch to pub/sub or message broker instead of directly setting 
  #       the handler
  @staticmethod
  def before_insert(mapper, connection, target):
    Versioned.before_db_change(mapper, connection, target, 'insert')

  @staticmethod
  def before_update(mapper, connection, target):
    obj_changed = False
    for col in target.__table__.columns:
      prop = mapper.get_property_by_column(col)
      if (prop.key != 'rev_id'
          and sa.orm.attributes.get_history(target, prop.key).has_changes()):
        obj_changed = True
        break
    if obj_changed:
      Versioned.before_db_change(mapper, connection, target, 'update')

  @staticmethod
  def before_delete(mapper, connection, target):
    Versioned.before_db_change(mapper, connection, target, 'delete')

  @staticmethod
  def before_db_change(mapper, connection, target, action):
    # target: re-roll the rev_id on change
    # this is needed for insert b/c we don't have init to populate its value
    target.rev_id = str(uuid.uuid4())

    # revision
    # todo: should we handle the defaults in a constructor?
    attr = aadict.aadict()
    attr.rev_id = getattr(target, 'rev_id')
    attr.rev_created = time.time()
    attr.rev_isdelete = False
    for k in target.__table__.primary_key:
      prop = mapper.get_property_by_column(k).key
      attr[k.name] = getattr(target, prop)

    if action == 'delete':
      attr.rev_isdelete = True
      # skips copying the rest of the fields (hence None)
    else:
      # todo: is there a better way to copy this?
      for c in target.__table__.c:
        # skip primary key and namespaced fields (already assigned)
        if not (c.name.startswith('rev_') or c.primary_key is True):
          prop = mapper.get_property_by_column(c).key
          attr[c.name] = getattr(target, prop)
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


  @staticmethod
  def create_rev_class(cls):
    # todo: validate autogenerate capabilities with alembic for 
    #       indexes, unique constraints, and foreign keys
    def _col_copy(col):
      ''''
      Copies column and removes nullable, constraints, and defaults. 
      '''
      col = col.copy()
      if col.primary_key is True:
        col.nullable = False
        col.index = True
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
    sa.event.listen(rev_cls, 'before_update', raiseUpdateForbidden)
    sa.event.listen(rev_cls, 'before_delete', raiseDeleteForbidden)

  @classmethod
  def versioned_session(cls, session):
    cls.DBSession = session


class DeleteForbidden(Exception): pass
def raiseDeleteForbidden(mapper, connection, target):
  raise DeleteForbidden('%r cannot be deleted' % (target,))

class UpdateForbidden(Exception): pass
def raiseUpdateForbidden(mapper, connection, target):
  raise UpdateForbidden('%r cannot be updated' % (target,))
