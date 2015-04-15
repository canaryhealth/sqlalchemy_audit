"""Unit tests illustrating usage of the ``history_meta.py``
module functions."""

from unittest import TestCase
from sqlalchemy.ext.declarative import declarative_base
from ..history_meta import Versioned, versioned_session
from sqlalchemy import create_engine, Column, Integer, String, \
    ForeignKey, Boolean, select
from sqlalchemy.orm import clear_mappers, Session, deferred, relationship, \
    column_property
from sqlalchemy.testing import AssertsCompiledSQL, eq_, assert_raises
from sqlalchemy.testing.entities import ComparableEntity
from sqlalchemy.orm import exc as orm_exc
import warnings

warnings.simplefilter("error")

engine = None


def setup_module():
    global engine
    engine = create_engine('sqlite://', echo=True)


class TestVersioning(TestCase, AssertsCompiledSQL):
    __dialect__ = 'default'

    def setUp(self):
        self.session = Session(engine)
        self.Base = declarative_base()
        versioned_session(self.session)

    def tearDown(self):
        self.session.close()
        clear_mappers()
        self.Base.metadata.drop_all(engine)

    def create_tables(self):
        self.Base.metadata.create_all(engine)

    def test_plain(self):
        class SomeClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'sometable'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        self.create_tables()
        sess = self.session
        sc = SomeClass(name='sc1')
        sess.add(sc)
        sess.commit()

        sc.name = 'sc1modified'
        sess.commit()

        assert sc.version == 2

        SomeClassAudit = SomeClass.__audit_mapper__.class_

        eq_(
            sess.query(SomeClassAudit).filter(
                SomeClassAudit.version == 1).all(),
            [SomeClassAudit(version=1, name='sc1')]
        )

        sc.name = 'sc1modified2'

        eq_(
            sess.query(SomeClassAudit).order_by(
                SomeClassAudit.version).all(),
            [
                SomeClassAudit(version=1, name='sc1'),
                SomeClassAudit(version=2, name='sc1modified')
            ]
        )

        assert sc.version == 3

        sess.commit()

        sc.name = 'temp'
        sc.name = 'sc1modified2'

        sess.commit()

        eq_(
            sess.query(SomeClassAudit).order_by(
                SomeClassAudit.version).all(),
            [
                SomeClassAudit(version=1, name='sc1'),
                SomeClassAudit(version=2, name='sc1modified')
            ]
        )

        sess.delete(sc)
        sess.commit()

        eq_(
            sess.query(SomeClassAudit).order_by(
                SomeClassAudit.version).all(),
            [
                SomeClassAudit(version=1, name='sc1'),
                SomeClassAudit(version=2, name='sc1modified'),
                SomeClassAudit(version=3, name='sc1modified2')
            ]
        )

    def test_w_mapper_versioning(self):
        class SomeClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'sometable'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        SomeClass.__mapper__.version_id_col = SomeClass.__table__.c.version

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

        eq_(sc.version, 2)

        assert_raises(
            orm_exc.StaleDataError,
            s2.flush
        )

    def test_from_null(self):
        class SomeClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'sometable'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        self.create_tables()
        sess = self.session
        sc = SomeClass()
        sess.add(sc)
        sess.commit()

        sc.name = 'sc1'
        sess.commit()

        assert sc.version == 2

    def test_insert_null(self):
        class SomeClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'sometable'

            id = Column(Integer, primary_key=True)
            boole = Column(Boolean, default=False)

        self.create_tables()
        sess = self.session
        sc = SomeClass(boole=True)
        sess.add(sc)
        sess.commit()

        sc.boole = None
        sess.commit()

        sc.boole = False
        sess.commit()

        SomeClassAudit = SomeClass.__audit_mapper__.class_

        eq_(
            sess.query(SomeClassAudit.boole).order_by(
                SomeClassAudit.id).all(),
            [(True, ), (None, )]
        )

        eq_(sc.version, 3)

    def test_deferred(self):
        """test versioning of unloaded, deferred columns."""

        class SomeClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'sometable'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            data = deferred(Column(String(25)))

        self.create_tables()
        sess = self.session
        sc = SomeClass(name='sc1', data='somedata')
        sess.add(sc)
        sess.commit()
        sess.close()

        sc = sess.query(SomeClass).first()
        assert 'data' not in sc.__dict__

        sc.name = 'sc1modified'
        sess.commit()

        assert sc.version == 2

        SomeClassAudit = SomeClass.__audit_mapper__.class_

        eq_(
            sess.query(SomeClassAudit).filter(
                SomeClassAudit.version == 1).all(),
            [SomeClassAudit(version=1, name='sc1', data='somedata')]
        )

    def test_joined_inheritance(self):
        class BaseClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'basetable'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            type = Column(String(20))

            __mapper_args__ = {
                'polymorphic_on': type,
                'polymorphic_identity': 'base'}

        class SubClassSeparatePk(BaseClass):
            __tablename__ = 'subtable1'

            id = column_property(
                Column(Integer, primary_key=True),
                BaseClass.id
            )
            base_id = Column(Integer, ForeignKey('basetable.id'))
            subdata1 = Column(String(50))

            __mapper_args__ = {'polymorphic_identity': 'sep'}

        class SubClassSamePk(BaseClass):
            __tablename__ = 'subtable2'

            id = Column(
                Integer, ForeignKey('basetable.id'), primary_key=True)
            subdata2 = Column(String(50))

            __mapper_args__ = {'polymorphic_identity': 'same'}

        self.create_tables()
        sess = self.session

        sep1 = SubClassSeparatePk(name='sep1', subdata1='sep1subdata')
        base1 = BaseClass(name='base1')
        same1 = SubClassSamePk(name='same1', subdata2='same1subdata')
        sess.add_all([sep1, base1, same1])
        sess.commit()

        base1.name = 'base1mod'
        same1.subdata2 = 'same1subdatamod'
        sep1.name = 'sep1mod'
        sess.commit()

        BaseClassAudit = BaseClass.__audit_mapper__.class_
        SubClassSeparatePkAudit = \
            SubClassSeparatePk.__audit_mapper__.class_
        SubClassSamePkAudit = SubClassSamePk.__audit_mapper__.class_
        eq_(
            sess.query(BaseClassAudit).order_by(BaseClassAudit.id).all(),
            [
                SubClassSeparatePkAudit(
                    id=1, name='sep1', type='sep', version=1),
                BaseClassAudit(id=2, name='base1', type='base', version=1),
                SubClassSamePkAudit(
                    id=3, name='same1', type='same', version=1)
            ]
        )

        same1.subdata2 = 'same1subdatamod2'

        eq_(
            sess.query(BaseClassAudit).order_by(
                BaseClassAudit.id, BaseClassAudit.version).all(),
            [
                SubClassSeparatePkAudit(
                    id=1, name='sep1', type='sep', version=1),
                BaseClassAudit(id=2, name='base1', type='base', version=1),
                SubClassSamePkAudit(
                    id=3, name='same1', type='same', version=1),
                SubClassSamePkAudit(
                    id=3, name='same1', type='same', version=2)
            ]
        )

        base1.name = 'base1mod2'
        eq_(
            sess.query(BaseClassAudit).order_by(
                BaseClassAudit.id, BaseClassAudit.version).all(),
            [
                SubClassSeparatePkAudit(
                    id=1, name='sep1', type='sep', version=1),
                BaseClassAudit(id=2, name='base1', type='base', version=1),
                BaseClassAudit(
                    id=2, name='base1mod', type='base', version=2),
                SubClassSamePkAudit(
                    id=3, name='same1', type='same', version=1),
                SubClassSamePkAudit(
                    id=3, name='same1', type='same', version=2)
            ]
        )

    def test_joined_inheritance_multilevel(self):
        class BaseClass(Versioned, self.Base, ComparableEntity):
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

        SubSubAudit = SubSubClass.__audit_mapper__.class_
        sess = self.session
        q = sess.query(SubSubAudit)
        self.assert_compile(
            q,


            "SELECT "

            "subsubtable_audit.id AS subsubtable_audit_id, "
            "subtable_audit.id AS subtable_audit_id, "
            "basetable_audit.id AS basetable_audit_id, "

            "subsubtable_audit.changed AS subsubtable_audit_changed, "
            "subtable_audit.changed AS subtable_audit_changed, "
            "basetable_audit.changed AS basetable_audit_changed, "

            "basetable_audit.name AS basetable_audit_name, "

            "basetable_audit.type AS basetable_audit_type, "

            "subsubtable_audit.version AS subsubtable_audit_version, "
            "subtable_audit.version AS subtable_audit_version, "
            "basetable_audit.version AS basetable_audit_version, "


            "subtable_audit.base_id AS subtable_audit_base_id, "
            "subtable_audit.subdata1 AS subtable_audit_subdata1, "
            "subsubtable_audit.subdata2 AS subsubtable_audit_subdata2 "
            "FROM basetable_audit "
            "JOIN subtable_audit "
            "ON basetable_audit.id = subtable_audit.base_id "
            "AND basetable_audit.version = subtable_audit.version "
            "JOIN subsubtable_audit ON subtable_audit.id = "
            "subsubtable_audit.id AND subtable_audit.version = "
            "subsubtable_audit.version"
        )

        ssc = SubSubClass(name='ss1', subdata1='sd1', subdata2='sd2')
        sess.add(ssc)
        sess.commit()
        eq_(
            sess.query(SubSubAudit).all(),
            []
        )
        ssc.subdata1 = 'sd11'
        ssc.subdata2 = 'sd22'
        sess.commit()
        eq_(
            sess.query(SubSubAudit).all(),
            [SubSubAudit(name='ss1', subdata1='sd1',
                                subdata2='sd2', type='subsub', version=1)]
        )
        eq_(ssc, SubSubClass(
            name='ss1', subdata1='sd11',
            subdata2='sd22', version=2))

    def test_joined_inheritance_changed(self):
        class BaseClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'basetable'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            type = Column(String(20))

            __mapper_args__ = {
                'polymorphic_on': type,
                'polymorphic_identity': 'base'
            }

        class SubClass(BaseClass):
            __tablename__ = 'subtable'

            id = Column(Integer, ForeignKey('basetable.id'), primary_key=True)

            __mapper_args__ = {'polymorphic_identity': 'sep'}

        self.create_tables()

        BaseClassAudit = BaseClass.__audit_mapper__.class_
        SubClassAudit = SubClass.__audit_mapper__.class_
        sess = self.session
        s1 = SubClass(name='s1')
        sess.add(s1)
        sess.commit()

        s1.name = 's2'
        sess.commit()

        actual_changed_base = sess.scalar(
            select([BaseClass.__audit_mapper__.local_table.c.changed]))
        actual_changed_sub = sess.scalar(
            select([SubClass.__audit_mapper__.local_table.c.changed]))
        h1 = sess.query(BaseClassAudit).first()
        eq_(h1.changed, actual_changed_base)
        eq_(h1.changed, actual_changed_sub)

        h1 = sess.query(SubClassAudit).first()
        eq_(h1.changed, actual_changed_base)
        eq_(h1.changed, actual_changed_sub)

    def test_single_inheritance(self):
        class BaseClass(Versioned, self.Base, ComparableEntity):
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

        b1 = BaseClass(name='b1')
        sc = SubClass(name='s1', subname='sc1')

        sess.add_all([b1, sc])

        sess.commit()

        b1.name = 'b1modified'

        BaseClassAudit = BaseClass.__audit_mapper__.class_
        SubClassAudit = SubClass.__audit_mapper__.class_

        eq_(
            sess.query(BaseClassAudit).order_by(
                BaseClassAudit.id, BaseClassAudit.version).all(),
            [BaseClassAudit(id=1, name='b1', type='base', version=1)]
        )

        sc.name = 's1modified'
        b1.name = 'b1modified2'

        eq_(
            sess.query(BaseClassAudit).order_by(
                BaseClassAudit.id, BaseClassAudit.version).all(),
            [
                BaseClassAudit(id=1, name='b1', type='base', version=1),
                BaseClassAudit(
                    id=1, name='b1modified', type='base', version=2),
                SubClassAudit(id=2, name='s1', type='sub', version=1)
            ]
        )

        # test the unique constraint on the subclass
        # column
        sc.name = "modifyagain"
        sess.flush()

    def test_unique(self):
        class SomeClass(Versioned, self.Base, ComparableEntity):
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

        assert sc.version == 2

        sc.data = 'sc1modified2'
        sess.commit()

        assert sc.version == 3

    def test_relationship(self):

        class SomeRelated(self.Base, ComparableEntity):
            __tablename__ = 'somerelated'

            id = Column(Integer, primary_key=True)

        class SomeClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'sometable'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            related_id = Column(Integer, ForeignKey('somerelated.id'))
            related = relationship("SomeRelated", backref='classes')

        SomeClassAudit = SomeClass.__audit_mapper__.class_

        self.create_tables()
        sess = self.session
        sc = SomeClass(name='sc1')
        sess.add(sc)
        sess.commit()

        assert sc.version == 1

        sr1 = SomeRelated()
        sc.related = sr1
        sess.commit()

        assert sc.version == 2

        eq_(
            sess.query(SomeClassAudit).filter(
                SomeClassAudit.version == 1).all(),
            [SomeClassAudit(version=1, name='sc1', related_id=None)]
        )

        sc.related = None

        eq_(
            sess.query(SomeClassAudit).order_by(
                SomeClassAudit.version).all(),
            [
                SomeClassAudit(version=1, name='sc1', related_id=None),
                SomeClassAudit(version=2, name='sc1', related_id=sr1.id)
            ]
        )

        assert sc.version == 3

    def test_backref_relationship(self):

        class SomeRelated(self.Base, ComparableEntity):
            __tablename__ = 'somerelated'

            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            related_id = Column(Integer, ForeignKey('sometable.id'))
            related = relationship("SomeClass", backref='related')

        class SomeClass(Versioned, self.Base, ComparableEntity):
            __tablename__ = 'sometable'

            id = Column(Integer, primary_key=True)

        self.create_tables()
        sess = self.session
        sc = SomeClass()
        sess.add(sc)
        sess.commit()

        assert sc.version == 1

        sr = SomeRelated(name='sr', related=sc)
        sess.add(sr)
        sess.commit()

        assert sc.version == 1

        sr.name = 'sr2'
        sess.commit()

        assert sc.version == 1

        sess.delete(sr)
        sess.commit()

        assert sc.version == 1
