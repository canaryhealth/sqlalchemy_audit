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


def col_references_table(col, table):
    for fk in col.foreign_keys:
        if fk.references(table):
            return True
    return False


def _is_audit_meta_col(col):
    return "audit_meta" in col.info


def _audit_mapper(local_mapper):
    cls = local_mapper.class_

    # set the "active_history" flag
    # on on column-mapped attributes so that the old version
    # of the info is always loaded (currently sets it on all attributes)
    for prop in local_mapper.iterate_properties:
        getattr(local_mapper.class_, prop.key).impl.active_history = True

    super_mapper = local_mapper.inherits
    super_audit_mapper = getattr(cls, '__audit_mapper__', None)

    polymorphic_on = None
    super_fks = []

    def _col_copy(col):
        orig = col
        col = col.copy()
        orig.info['audit_copy'] = col
        col.unique = False
        col.default = col.server_default = None
        return col

    properties = util.OrderedDict()
    if not super_mapper or \
            local_mapper.local_table is not super_mapper.local_table:
        cols = []
        # add column.info to identify columns used for auditing
        audit_meta = {"audit_meta": True}  

        for column in local_mapper.local_table.c:
            if _is_audit_meta_col(column):
                continue

            col = _col_copy(column)

            if super_mapper and \
                    col_references_table(column, super_mapper.local_table):
                super_fks.append(
                    (
                        col.key,
                        list(super_audit_mapper.local_table.primary_key)[0]
                    )
                )

            cols.append(col)

            if column is local_mapper.polymorphic_on:
                polymorphic_on = col

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

        # audit meta columns (see _is_audit_meta_col)
        #   - audit record id
        #   - UTC timestamp of when the audit row was created
        #   - boolean flag to identify that this record has since been deleted
        cols.append(Column('audit_rec_id', String, primary_key=True,
                           default=lambda:str(uuid.uuid4()), info=audit_meta))
        cols.append(Column('audit_timestamp', Float, default=time.time,
                           info=audit_meta))
        cols.append(Column('audit_isdelete', Boolean, default=False,
                           info=audit_meta))

        if super_fks:
            cols.append(ForeignKeyConstraint(*zip(*super_fks)))

        table = Table(
            local_mapper.local_table.name + '_audit',
            local_mapper.local_table.metadata,
            *cols,
            schema=local_mapper.local_table.schema
        )
    else:
        # single table inheritance.  take any additional columns that may have
        # been added and add them to the audit table.
        for column in local_mapper.local_table.c:
            if column.key not in super_audit_mapper.local_table.c:
                col = _col_copy(column)
                super_audit_mapper.local_table.append_column(col)
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
        def map(cls, *arg, **kw):
            mp = mapper(cls, *arg, **kw)
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

    obj_changed = False

    for om, am in zip(
            obj_mapper.iterate_to_root(),
            audit_mapper.iterate_to_root()
    ):
        # why do we skip if it's a single table inheritance mapper
        if am.single:
            continue

        for hist_col in am.local_table.c:            
            if _is_audit_meta_col(hist_col):
                continue

            obj_col = om.local_table.c[hist_col.key]

            # get the value of the
            # attribute based on the MapperProperty related to the
            # mapped column.  this will allow usage of MapperProperties
            # that have a different keyname than that of the mapped column.
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

            a, u, d = attributes.get_history(obj, prop.key)

            if d:
                attr[hist_col.key] = getattr(obj, prop.key)
                obj_changed = True
            elif u:
                attr[hist_col.key] = getattr(obj, prop.key)
            else:
                # if the attribute had no value.
                attr[hist_col.key] = a[0]
                obj_changed = True

    if not obj_changed:
        # not changed, but we have relationships.  OK
        # check those too
        for prop in obj_mapper.iterate_properties:
            if isinstance(prop, RelationshipProperty) and \
                attributes.get_history(
                    obj, prop.key,
                    passive=attributes.PASSIVE_NO_INITIALIZE).has_changes():
                for p in prop.local_columns:
                    if p.foreign_keys:
                        obj_changed = True
                        break
                if obj_changed is True:
                    break

    #if not obj_changed and not deleted:
    #    return

    audit_copy = audit_cls()
    for key, value in attr.items():
        setattr(audit_copy, key, value)
    if deleted:
        setattr(audit_copy, 'audit_isdelete', True)
    session.add(audit_copy)


def auditable_session(session):
    @event.listens_for(session, 'before_flush')
    def before_flush(session, flush_context, instances):
        for obj in auditable_objects(session.new):
            create_record(obj, session, new=True)
        for obj in auditable_objects(session.dirty):
            create_record(obj, session)
        for obj in auditable_objects(session.deleted):
            create_record(obj, session, deleted=True)
