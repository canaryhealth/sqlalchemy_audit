================
sqlalchemy-audit
================

sqlalchemy-audit provides an easy way to set up audit tables for your data. It is built on top of a heavily modified version of SQLAlchemy's ``versioned_history`` example.


Example
=======

Simply declare your class as usual, then subclass ``Auditable`` and specify audit record:

.. code:: python

  class Reservation(Auditable, Base):
    __tablename__ = 'reservation'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    date = Column(Date)
    time = Column(Time)
    party = Column(Integer)
    last_modified = Column(DateTime)

    audit = sa_audit.record(prefix='audit_', ...)


.. note:: You can also sub-class ``Auditable`` from your declarative base class. 


Normal usage remains the same:

.. code:: python

  # make new reservation
  steve_reservation = Reservation(name='Steve', 
                                  date=datetime.date(2015, 04, 15),
                                  time=datetime.time(19, 00),
                                  party=6)
  session.add(steve_reservation)
  session.commit()

  # change reservation to party of 4
  steve_reservation.party = 4
  session.commit()


Plus, you could access its audit/history.

.. code:: python

  >>> print steve_reservation.audit.records()
  [ ReservationAudit(audit_id='c74d5bce...', audit_timestamp=1427995346.0, audit_isdelete=False, id=1, name='Steve', date='2015-04-15', time='19:00', party=6, last_modified='2015-04-02 13:22:26.291670'),
    ReservationAudit(audit_id='f3f5091d...', audit_timestamp=1428068391.0, audit_isdelete=False, id=1, name='Steve', date='2015-04-15', time='19:00', party=4, last_modified='2015-04-03 09:39:51.098798'),
    ReservationAudit(audit_id='3cf1394b...', audit_timestamp=1428534191.0, audit_isdelete=True, id=1, name=None, date=None, time=None, party=None, last_modified=None)
  ]


How it works
============

Suppose you have a ``reservations`` table.

==  ======  ==========  =====  =====  ==========================
id  name    date        time   party  last_modified
==  ======  ==========  =====  =====  ==========================
 1  Steve   2015-04-15  19:00  4      2015-04-08 13:22:26.291670
 2  Phil    2015-05-01  18:30  3      2015-04-13 09:38:01.060898
==  ======  ==========  =====  =====  ==========================


Behind the scenes, we create an audit table ``reservations_audit`` with the same schema with three additional columns:

  audit_id : string (uuid)
    Surrogate key for the audit table.

  audit_timestamp : timestamp
    Timestamp (seconds since the epoch as a floating point number) of when the audit entry was created. (See `Use of audit_timestamp`_.)

  audit_isdelete : boolean
    Whether the entry was deleted. (See `Use of audit_isdelete`_.)


Whenever you write to the ``reservations`` table, we will insert a new row into the ``reservations_audit`` table. This allows your usage of ``reservations`` to remain unchanged. If need, you could reference the ``reservations_audit`` to get the timelime.


Example
-------

For the following timeline:

- On 2015-04-02, Steve makes a reservation for party of 6 on 2015-04-15 at 19:30.
- On 2015-04-03, Steve changes the reservation to 4 people.
- On 2015-04-08, Steve cancels the reservation.


``reservations_audit`` will have the following 

===========  ===============  ==============  ======  ======  ==========  ======  ======  ==========================
audit_id     audit_timestamp  audit_isdelete  id      name    date        time    party   last_modified
===========  ===============  ==============  ======  ======  ==========  ======  ======  ==========================
c74d5bce...  1427995346.0     False           1       Steve   2015-04-15  19:00   6       2015-04-02 13:22:26.291670
f3f5091d...  1428068391.0     False           1       Steve   2015-04-15  19:00   4       2015-04-03 09:39:51.098798
3cf1394b...  1428534191.0     True            1       (null)  (null)      (null)  (null)  (null)
===========  ===============  ==============  ======  ======  ==========  ======  ======  ==========================



Design Decisions
----------------

Writing to audit table for all writes
`````````````````````````````````````

There are several advantages by writing to the audit table for all writes:

  1. complete transaction history in the audit table for easy reads (no joins required)
  2. complete timeline even if the original table doesn't have a last modified column


However, this approach has a particular drawback with ``INSERT`` statements with dynamic defaults (such as sequences or auto-datetime). At the time of the insert, the audit able does not have the dynamic values. We recommend the following workarounds:

  1. generate dynamic defaults during object instantiation instead of the database
  2. strictly use client-side defaults in the ORM
  3. create server-side database triggers to copy values to audit table for inserts
  4. perform a write-read-write transaction for inserts, which is sub-optimal due to the performance hit


Use of audit_timestamp
``````````````````````

To re-create the audit timeline, we are relying on the use of timestamps. While we recognize there could be clock drift or desynchronization across different servers, there are solutions to these problems. Hence we opt to proceed with timestamp's simplicity.


Use of audit_isdelete
`````````````````````

The ``audit_isdelete`` is a fast and convenient way to determined that a row has been deleted without inspecting the entries. It also allows for entries with all nulls.


Requirement of primary/compound keys
````````````````````````````````````

TBD


Requirement of association objects for many-to-many relationships
`````````````````````````````````````````````````````````````````

TBD
