"""Auditable mixin class and other utilities."""
import time
import uuid

from sqlalchemy import Table, Column, Boolean, Float, String, \
    ForeignKeyConstraint
from sqlalchemy import event, util
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import mapper, attributes, object_mapper
from sqlalchemy.orm.exc import UnmappedColumnError
from sqlalchemy.orm.properties import RelationshipProperty


def _is_audit_meta_col(col):
    return "audit_meta" in col.info


def _audit_mapper(local_mapper):
    cls = local_mapper.class_

    super_mapper = local_mapper.inherits
    super_audit_mapper = getattr(cls, '__audit_mapper__', None)

    polymorphic_on = None
    super_fks = []

    def _col_copy(col):
        ''''
        Copies column, adds copied col reference to original column, removes 
        unique constraints and column defaults. 
        '''
        orig = col
        col = col.copy()
        orig.info['audit_copy'] = col
        col.unique = False
        col.default = col.server_default = None
        return col

    properties = util.OrderedDict()
    # create audit table if it does not exist
    if not super_mapper or \
            local_mapper.local_table is not super_mapper.local_table:
        audit_cols = []
        # add to column.info to identify columns used for auditing
        audit_meta = {"audit_meta": True}  
        # audit meta columns (see _is_audit_meta_col)
        #   - audit record id
        #   - UTC timestamp of when the audit row was created
        #   - boolean flag to identify that this record has since been deleted
        audit_cols.append(Column('audit_rec_id', String, primary_key=True,
                                 default=lambda:str(uuid.uuid4()), 
                                 info=audit_meta))
        audit_cols.append(Column('audit_timestamp', Float, default=time.time,
                                 info=audit_meta))
        audit_cols.append(Column('audit_isdelete', Boolean, default=False,
                                 info=audit_meta))

        for column in local_mapper.local_table.c:
            if _is_audit_meta_col(column):
                continue

            audit_col = _col_copy(column)
            # if there is a fk between local_mapper and super_mapper, set up 
            # same for local_audit_mapper and super_audit_mapper
            if super_mapper:
                for fk in column.foreign_keys:
                    if fk.references(super_mapper.local_table):
                        super_fks.append(
                            (audit_col.key,
                             super_audit_mapper.local_table.c[fk.column.name])
                        )
            audit_cols.append(audit_col)

            if column is local_mapper.polymorphic_on:
                polymorphic_on = audit_col

            orig_prop = local_mapper.get_property_by_column(column)
            # carry over column re-mappings
            if len(orig_prop.columns) > 1 or \
                    orig_prop.columns[0].key != orig_prop.key:
                properties[orig_prop.key] = tuple(
                    col.info['audit_copy'] for col in orig_prop.columns)

        if super_mapper:
            super_fks.append(
                ('audit_rec_id', super_audit_mapper.local_table.c.audit_rec_id)
            )

        if super_fks:
            audit_cols.append(ForeignKeyConstraint(*zip(*super_fks)))

        table = Table(
            local_mapper.local_table.name + '_audit',
            local_mapper.local_table.metadata,
            *audit_cols,
            schema=local_mapper.local_table.schema
        )
    # single table inheritance. take any additional columns that may have
    # been added and add them to the audit table.
    else:
        for column in local_mapper.local_table.c:
            if column.key not in super_audit_mapper.local_table.c:
                audit_col = _col_copy(column)
                super_audit_mapper.local_table.append_column(audit_col)
        table = None


    if super_audit_mapper:
        bases = (super_audit_mapper.class_,)

        if table is not None:
            properties['audit_timestamp'] = (
                (table.c.audit_timestamp, ) +
                tuple(super_audit_mapper.attrs.audit_timestamp.columns)
            )
    else:
        bases = local_mapper.base_mapper.class_.__bases__
    auditable_cls = type.__new__(type, "%sAudit" % cls.__name__, bases, {})

    m = mapper(
        auditable_cls,
        table,
        inherits=super_audit_mapper,
        polymorphic_on=polymorphic_on,
        polymorphic_identity=local_mapper.polymorphic_identity,
        properties=properties
    )
    cls.__audit_mapper__ = m


class Auditable(object):
    @declared_attr
    def __mapper_cls__(cls):
        def map(cls, *arg, **kwargs):
            mp = mapper(cls, *arg, **kwargs)
            _audit_mapper(mp)
            return mp
        return map


def auditable_objects(iter):
    for obj in iter:
        if hasattr(obj, '__audit_mapper__'):
            yield obj


def create_record(obj, session, new=False, deleted=False):
    obj_mapper = object_mapper(obj)
    audit_mapper = obj.__audit_mapper__
    audit_cls = audit_mapper.class_

    obj_state = attributes.instance_state(obj)

    attr = {}

    for om, am in zip(obj_mapper.iterate_to_root(),
                      audit_mapper.iterate_to_root()):
        # why do we skip if it's a single table inheritance mapper
        if am.single:
            continue

        # loop thru audit columns and copy original values over (except for 
        # deletes)
        for audit_column in am.local_table.c:            
            if _is_audit_meta_col(audit_column):
                continue

            obj_col = om.local_table.c[audit_column.key]
            # get the value of the attribute based on the MapperProperty 
            # related to the mapped column. this will allow usage of 
            # MapperProperties that have a different keyname than that of the
            # mapped column.
            try:
                prop = obj_mapper.get_property_by_column(obj_col)
            except UnmappedColumnError:
                # in the case of single table inheritance, there may be
                # columns on the mapped table intended for the subclass only.
                # the "unmapped" status of the subclass column on the
                # base class is a feature of the declarative module.
                continue
            # expired object attributes and also deferred cols might not
            # be in the dict.  force it to load no matter what by
            # using getattr().
            if prop.key not in obj_state.dict:
                getattr(obj, prop.key)

            # set audit_copy to None if delete and not primary key
            if deleted and not audit_column.primary_key:
                attr[audit_column.key] = None
            else:
                attr[audit_column.key] = getattr(obj, prop.key)

    # create audit record
    audit_copy = audit_cls()
    for key, value in attr.items():
        setattr(audit_copy, key, value)
    if deleted:
        setattr(audit_copy, 'audit_isdelete', True)
    session.add(audit_copy)


def auditable_session(session):
    # since we are creating an audit record for every write, we need to use
    # after_flush because client-side defaults and relationship ids are 
    # populated after flush
    @event.listens_for(session, 'after_flush')
    def after_flush(session, flush_context):
        for obj in auditable_objects(session.new):
            create_record(obj, session, new=True)
        for obj in auditable_objects(session.dirty):
            create_record(obj, session)
        for obj in auditable_objects(session.deleted):
            create_record(obj, session, deleted=True)
