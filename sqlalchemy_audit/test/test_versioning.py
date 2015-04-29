"""Unit tests illustrating usage of the ``history_meta.py``
module functions."""
import morph
import unittest
import uuid
import warnings

from sqlalchemy import create_engine, Column, Integer, String, \
    ForeignKey, Boolean, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import clear_mappers, Session, deferred, relationship, \
    column_property
from sqlalchemy.orm import exc as orm_exc
from sqlalchemy.testing import AssertsCompiledSQL, eq_, assert_raises
from sqlalchemy.testing.entities import ComparableEntity

from ..history_meta import Auditable, auditable_session


warnings.simplefilter("error")

engine = None


def setup_module():
    global engine
    engine = create_engine('sqlite://', echo=True)


class TestVersioning(unittest.TestCase, AssertsCompiledSQL):
    __dialect__ = 'default'

    def assertSeqEqual(self, result, expected, pick=None):
        if pick is not None and morph.isseq(result) and morph.isseq(expected):
            result = [morph.pick(item, *morph.tolist(pick)) for item in result]
            expected = [morph.pick(item, *morph.tolist(pick)) for item in expected]

        self.assertEqual(result, expected, 'the lists are different')


    def setUp(self):
        self.session = Session(engine)
        self.Base = declarative_base()
        auditable_session(self.session)

    def tearDown(self):
        self.session.close()
        clear_mappers()
        self.Base.metadata.drop_all(engine)

    def create_tables(self):
        self.Base.metadata.create_all(engine)

    '''
    def test_w_mapper_versioning(self):
        class SomeClass(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'sometable'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        SomeClass.__mapper__.version_id_col = SomeClass.__table__.c.audit_rec_id

        self.create_tables()
        sess = self.session
        sc = SomeClass(name='sc1')
        sess.add(sc)
        sess.commit()

        s2 = Session(sess.bind)
        sc2 = s2.query(SomeClass).first()
        sc2.name = 'sc1modified'

        sc.name = 'sc1modified_again'
        sess.commit()

        eq_(sc.audit_rec_id, 2)

        assert_raises(
            orm_exc.StaleDataError,
            s2.flush
        )
    '''

    def test_deferred(self):
        class SomeClass(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'sometable'
            id = Column(String, primary_key=True)
            name = Column(String(50))
            data = deferred(Column(String(25)))

        self.create_tables()
        sess = self.session
        sc = SomeClass(id=str(uuid.uuid4()), name='sc1', data='somedata')
        sess.add(sc)
        sess.commit()
        sess.close()

        sc = sess.query(SomeClass).first()
        assert 'data' not in sc.__dict__

        sc.name = 'sc1modified'
        sess.commit()

        SomeClassAudit = SomeClass.__audit_mapper__.class_

        self.assertSeqEqual(
            sess.query(SomeClassAudit).all(),
            [
                SomeClassAudit(id=sc.id, name='sc1', data='somedata', 
                               audit_isdelete=False),
                SomeClassAudit(id=sc.id, name='sc1modified', data='somedata', 
                               audit_isdelete=False),
            ],
            pick=('id', 'name', 'data', 'audit_isdelete')
        )


    def test_joined_inheritance(self):
        class BaseClass(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'basetable'
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            type = Column(String(20))
            __mapper_args__ = {
                'polymorphic_on': type,
                'polymorphic_identity': 'base'}

        class SubClassSamePk(BaseClass):
            __tablename__ = 'subtablesame'
            id = Column(
                Integer, ForeignKey('basetable.id'), primary_key=True)
            subdata1 = Column(String(50))
            __mapper_args__ = {'polymorphic_identity': 'same'}

        class SubClassSeparatePk(BaseClass):
            __tablename__ = 'subtablesep'
            id = column_property(
                Column(Integer, primary_key=True),
                BaseClass.id
            )
            base_id = Column(Integer, ForeignKey('basetable.id'))
            subdata2 = Column(String(50))
            __mapper_args__ = {'polymorphic_identity': 'sep'}

        self.create_tables()
        sess = self.session

        # inserts
        base1 = BaseClass(name='base1')
        same1 = SubClassSamePk(name='same1', subdata1='same1subdata')
        sep1 = SubClassSeparatePk(name='sep1', subdata2='sep1subdata')
        sess.add(base1); sess.commit();
        sess.add(same1); sess.commit();
        sess.add(sep1); sess.commit();
        # updates
        base1.name = 'base1mod'; sess.commit();
        same1.subdata1 = 'same1subdatamod'; sess.commit();
        sep1.name = 'sep1mod'; sess.commit();
        same1.subdata1 = 'same1subdatamod2'; sess.commit();
        base1.name = 'base1mod2'; sess.commit();

        BaseClassAudit = BaseClass.__audit_mapper__.class_
        SubClassSamePkAudit = SubClassSamePk.__audit_mapper__.class_
        SubClassSeparatePkAudit = SubClassSeparatePk.__audit_mapper__.class_

        # assert foreign keys
        # basetable_audit.id : subtablesame_audit.id
        self.assertTrue(
            BaseClass.__audit_mapper__.local_table.c.id in \
            [i.column for i in list(SubClassSamePk.__audit_mapper__.local_table.c.id.foreign_keys)]
        )
        # basetable_audit.id : subtablesep_audit.base_id
        self.assertTrue(
            BaseClass.__audit_mapper__.local_table.c.id in \
            [i.column for i in list(SubClassSeparatePk.__audit_mapper__.local_table.c.base_id.foreign_keys)]
        )
        # basetable_audit.audit_rec_id : subtablesame_audit.audit_rec_id
        self.assertTrue(
            BaseClass.__audit_mapper__.local_table.c.audit_rec_id in \
            [i.column for i in list(SubClassSeparatePk.__audit_mapper__.local_table.c.audit_rec_id.foreign_keys)]
        )
        # basetable_audit.audit_rec_id : subtablesep_audit.audit_rec_id
        self.assertTrue(
            BaseClass.__audit_mapper__.local_table.c.audit_rec_id in \
            [i.column for i in list(SubClassSeparatePk.__audit_mapper__.local_table.c.audit_rec_id.foreign_keys)]
        )

        # assert data
        self.assertSeqEqual(
            sess.query(BaseClassAudit).order_by(BaseClassAudit.audit_timestamp).all(),
            [
                BaseClassAudit(
                    id=base1.id, name='base1', type='base', audit_isdelete=False),
                SubClassSamePkAudit(
                    id=same1.id, name='same1', type='same', audit_isdelete=False),
                SubClassSeparatePkAudit(
                    id=sep1.id, name='sep1', type='sep', audit_isdelete=False),
                BaseClassAudit(
                    id=base1.id, name='base1mod', type='base', audit_isdelete=False),
                SubClassSamePkAudit(
                    id=same1.id, name='same1', type='same', audit_isdelete=False),
                SubClassSeparatePkAudit(
                    id=sep1.id, name='sep1mod', type='sep', audit_isdelete=False),
                SubClassSamePkAudit(
                    id=same1.id, name='same1', type='same', audit_isdelete=False),
                BaseClassAudit(
                    id=base1.id, name='base1mod2', type='base', audit_isdelete=False),
            ],
            pick=('id', 'name', 'type', 'audit_isdelete')
        )
        self.assertSeqEqual(
            sess.query(SubClassSamePkAudit).order_by(SubClassSamePkAudit.audit_timestamp).all(),
            [
                SubClassSamePkAudit(id=same1.id, subdata1='same1subdata'),
                SubClassSamePkAudit(id=same1.id, subdata1='same1subdatamod'),
                SubClassSamePkAudit(id=same1.id, subdata1='same1subdatamod2'),
            ],
            pick=('subdata1')
        )
        self.assertSeqEqual(
            sess.query(SubClassSeparatePkAudit).order_by(SubClassSeparatePkAudit.audit_timestamp).all(),
            [
                SubClassSeparatePkAudit(base_id=sep1.id, subdata2='sep1subdata'),
                SubClassSeparatePkAudit(base_id=sep1.id, subdata2='sep1subdata'),
            ],
            pick=('base_id', 'subdata2')
        )


    def test_joined_inheritance_multilevel(self):
        class BaseClass(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'basetable'
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            type = Column(String(20))
            __mapper_args__ = {
                'polymorphic_on': type,
                'polymorphic_identity': 'base'}

        class SubClass(BaseClass):
            __tablename__ = 'subtable'
            id = column_property(
                Column(Integer, primary_key=True),
                BaseClass.id
            )
            base_id = Column(Integer, ForeignKey('basetable.id'))
            subdata1 = Column(String(50))
            __mapper_args__ = {'polymorphic_identity': 'sub'}

        class SubSubClass(SubClass):
            __tablename__ = 'subsubtable'
            id = Column(Integer, ForeignKey('subtable.id'), primary_key=True)
            subdata2 = Column(String(50))
            __mapper_args__ = {'polymorphic_identity': 'subsub'}

        self.create_tables()
        sess = self.session

        SubSubAudit = SubSubClass.__audit_mapper__.class_
        q = sess.query(SubSubAudit)

        self.assert_compile(
            q,
            "SELECT "
            "subsubtable_audit.id AS subsubtable_audit_id, "
            "subtable_audit.id AS subtable_audit_id, "
            "basetable_audit.id AS basetable_audit_id, "

            "subsubtable_audit.audit_timestamp AS subsubtable_audit_audit_timestamp, "
            "subtable_audit.audit_timestamp AS subtable_audit_audit_timestamp, "
            "basetable_audit.audit_timestamp AS basetable_audit_audit_timestamp, "

            "subsubtable_audit.audit_rec_id AS subsubtable_audit_audit_rec_id, "
            "subtable_audit.audit_rec_id AS subtable_audit_audit_rec_id, "
            "basetable_audit.audit_rec_id AS basetable_audit_audit_rec_id, "

            "subsubtable_audit.audit_isdelete AS subsubtable_audit_audit_isdelete, "
            "subtable_audit.audit_isdelete AS subtable_audit_audit_isdelete, "
            "basetable_audit.audit_isdelete AS basetable_audit_audit_isdelete, "

            "basetable_audit.name AS basetable_audit_name, "
            "basetable_audit.type AS basetable_audit_type, "

            "subtable_audit.base_id AS subtable_audit_base_id, "
            "subtable_audit.subdata1 AS subtable_audit_subdata1, "
            "subsubtable_audit.subdata2 AS subsubtable_audit_subdata2 "
            "FROM basetable_audit "
            "JOIN subtable_audit "
            "ON basetable_audit.audit_rec_id = subtable_audit.audit_rec_id "
            "AND basetable_audit.id = subtable_audit.base_id "
            "JOIN subsubtable_audit "
            "ON subtable_audit.audit_rec_id = subsubtable_audit.audit_rec_id "
            "AND subtable_audit.id = subsubtable_audit.id"
        )

        ssc = SubSubClass(name='ss1', subdata1='sd1', subdata2='sd2')
        sess.add(ssc)
        sess.commit()
        ssc.subdata1 = 'sd11'
        ssc.subdata2 = 'sd22'
        sess.commit()

        # assert source
        self.assertSeqEqual(
            sess.query(SubSubClass).all(),
            [ssc],
            pick=('id', 'name', 'subdata1', 'subdata2')
        )

        # assert audit records
        self.assertSeqEqual(
            sess.query(SubSubAudit).order_by(SubSubAudit.audit_timestamp).all(),
            [
                SubSubAudit(id=ssc.id, name='ss1', subdata1='sd1', subdata2='sd2', type='subsub'),
                SubSubAudit(id=ssc.id, name='ss1', subdata1='sd11', subdata2='sd22', type='subsub'),
            ],
            pick=('id', 'name', 'subdata1', 'subdata2', 'type')
        )


    def test_single_inheritance(self):
        class BaseClass(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'basetable'
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            type = Column(String(50))
            __mapper_args__ = {
                'polymorphic_on': type,
                'polymorphic_identity': 'base'}

        class SubClass(BaseClass):
            subname = Column(String(50), unique=True)
            __mapper_args__ = {'polymorphic_identity': 'sub'}

        self.create_tables()
        sess = self.session

        BaseClassAudit = BaseClass.__audit_mapper__.class_
        SubClassAudit = SubClass.__audit_mapper__.class_

        b1 = BaseClass(name='b1')
        sc = SubClass(name='s1', subname='sc1')
        sess.add(b1); sess.commit();
        sess.add(sc); sess.commit();

        b1.name = 'b1modified'; sess.commit();
        sc.subname = 'sc1sn'; sess.commit();
        b1.name = 'b1modified2'; sess.commit();
        sc.name = 's1modified2'; sess.commit();
        
        # assert source
        self.assertSeqEqual(
            sess.query(BaseClass).all(),
            [b1, sc],
            pick=('id', 'name', 'type', 'subname')
        )

        # assert audit records
        self.assertSeqEqual(
            sess.query(BaseClassAudit).order_by(BaseClassAudit.audit_timestamp).all(),
            [
                BaseClassAudit(id=b1.id, type='base', name='b1'),
                SubClassAudit(id=sc.id, type='sub', name='s1', subname='sc1'),
                BaseClassAudit(id=b1.id, type='base', name='b1modified'),
                SubClassAudit(id=sc.id, type='sub', name='s1', subname='sc1sn'),
                BaseClassAudit(id=b1.id, type='base', name='b1modified2'),
                SubClassAudit(id=sc.id, type='sub', name='s1modified2', subname='sc1sn'),
            ],
            pick=('id', 'name', 'type', 'subname')
        )


    def test_unique(self):
        class SomeClass(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'sometable'
            id = Column(Integer, primary_key=True)
            name = Column(String(50), unique=True)
            data = Column(String(50))

        self.create_tables()
        sess = self.session

        sc = SomeClass(name='sc1', data='sc1')
        sess.add(sc)
        sess.commit()
        sc.data = 'sc1modified'
        sess.commit()
        sc.name = 'sc1modified'
        sc.data = 'sc1modified2'
        sess.commit()

        SomeClassAudit = SomeClass.__audit_mapper__.class_

        # assert audit records
        self.assertSeqEqual(
            sess.query(SomeClassAudit).order_by(SomeClassAudit.audit_timestamp).all(),
            [
                SomeClassAudit(id=sc.id, name='sc1', data='sc1'),
                SomeClassAudit(id=sc.id, name='sc1', data='sc1modified'),
                SomeClassAudit(id=sc.id, name='sc1modified', data='sc1modified2'),
            ],
            pick=('id', 'name', 'data')
        )


    def test_relationship(self):
        class SomeClass(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'sometable'
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            related_id = Column(Integer, ForeignKey('somerelated.id'))
            related = relationship("SomeRelated", backref='classes')

        class SomeRelated(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'somerelated'
            id = Column(Integer, primary_key=True)
            desc = Column(String(50))

        SomeClassAudit = SomeClass.__audit_mapper__.class_
        SomeRelatedAudit = SomeRelated.__audit_mapper__.class_

        self.create_tables()
        sess = self.session
        sc1 = SomeClass(name='sc1')
        sess.add(sc1)
        sess.commit()
        sr1 = SomeRelated(desc='sr1')
        sc1.related = sr1
        sess.commit()

        # assert source
        self.assertSeqEqual(
            self.session.query(SomeClass).all(),
            [sc1],
            pick=('id', 'name')
        )
        self.assertSeqEqual(
            self.session.query(SomeRelated).all(),
            [sr1],
            pick=('id', 'desc')
        )

        # assert audit records
        self.assertSeqEqual(
            sess.query(SomeClassAudit).order_by(SomeClassAudit.audit_timestamp).all(),
            [
                SomeClassAudit(id=sc1.id, name='sc1', related_id=None),
                SomeClassAudit(id=sc1.id, name='sc1', related_id=sr1.id),
            ],
            pick=('id', 'name', 'related_id')
        )
        self.assertSeqEqual(
            sess.query(SomeRelatedAudit).order_by(SomeRelatedAudit.audit_timestamp).all(),
            [
                SomeRelatedAudit(id=sr1.id, desc='sr1')
            ],
            pick=('id', 'desc')
        )


    def test_backref_relationship(self):
        class SomeClass(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'sometable'
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        class SomeRelated(Auditable, self.Base, ComparableEntity):
            __tablename__ = 'somerelated'
            id = Column(Integer, primary_key=True)
            desc = Column(String(50))
            related_id = Column(Integer, ForeignKey('sometable.id'))
            related = relationship("SomeClass", backref='related')

        SomeClassAudit = SomeClass.__audit_mapper__.class_
        SomeRelatedAudit = SomeRelated.__audit_mapper__.class_

        self.create_tables()
        sess = self.session
        sc1 = SomeClass(name='sc1')
        sess.add(sc1)
        sess.commit()
        sr1 = SomeRelated(desc='sr1', related=sc1)
        sess.add(sr1)
        sess.commit()
        sr1.desc = 'sr2'
        sess.commit()
        sess.delete(sr1)
        sess.commit()

        # assert source
        self.assertSeqEqual(
            self.session.query(SomeClass).all(),
            [sc1],
            pick=('id', 'name')
        )
        self.assertSeqEqual(
            self.session.query(SomeRelated).all(),
            [],
            pick=('id', 'desc')
        )

        # assert audit records
        self.assertSeqEqual(
            sess.query(SomeClassAudit).order_by(SomeClassAudit.audit_timestamp).all(),
            [
                SomeClassAudit(id=sc1.id, name='sc1'),
            ],
            pick=('id', 'name')
        )
        self.assertSeqEqual(
            sess.query(SomeRelatedAudit).order_by(SomeRelatedAudit.audit_timestamp).all(),
            [
                SomeRelatedAudit(id=sr1.id, desc='sr1', related_id=sc1.id,
                                 audit_isdelete=False),
                SomeRelatedAudit(id=sr1.id, desc='sr2', related_id=sc1.id,
                                 audit_isdelete=False),
                SomeRelatedAudit(id=sr1.id, desc=None, related_id=None,
                                 audit_isdelete=True),
            ],
            pick=('id', 'desc', 'audit_isdelete')
        )
