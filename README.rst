================
sqlalchemy-audit
================

sqlalchemy-audit provides an easy way to set up revision tracking for your data. It is inspired by SQLAlchemy's ``versioned_history`` example, but uses mapper events instead of session events.


Example
=======

Share your ``DBSession`` with ``Versioned``:

.. code:: python

  DBSession = ...
  Versioned.versioned_session(DBSession)

Then simply declare your class as usual and have it inherit ``Versioned``:

.. code:: python

  class Reservation(Versioned, Base):
    __tablename__ = 'reservation'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    date = Column(Date)
    time = Column(Time)
    party = Column(Integer)
    last_modified = Column(DateTime)

  Reservation.broadcast_crud()  # todo: handle this automagically


.. note:: You can also sub-class ``Versioned`` from your declarative base class.


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

  # cancel the reservation
  session.delete(steve_reservation)
  session.commit()


Plus, you could access its revision history.

.. code:: python

  >>> DBSession.query(ReservationRev).all()
  [ ReservationRev(rev_id='c74d5bce...', rev_created=1427995346.0, rev_isdelete=False, id=1, name='Steve', date='2015-04-15', time='19:00', party=6, last_modified='2015-04-02 13:22:26.291670'),
    ReservationRev(rev_id='f3f5091d...', rev_created=1428068391.0, rev_isdelete=False, id=1, name='Steve', date='2015-04-15', time='19:00', party=4, last_modified='2015-04-03 09:39:51.098798'),
    ReservationRev(rev_id='3cf1394b...', rev_created=1428534191.0, rev_isdelete=True, id=1, name=None, date=None, time=None, party=None, last_modified=None)
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


Behind the scenes, we create an revision class ``ReservationRev`` mapped to table ``reservations_rev``. It has the same schema with three additional columns:

  rev_id : string (uuid)
    Surrogate key for the revision table.

  rev_created : timestamp
    Timestamp (seconds since the epoch as a floating point number) of when the revision was created. (See `Use of rev_created`_.)

  rev_isdelete : boolean
    Whether the entry was deleted. (See `Use of rev_isdelete`_.)


Whenever you write to the ``reservations`` table, we will insert a new row into the ``reservations_rev`` table. This allows your usage of ``reservations`` to remain unchanged. If need, you could reference the ``reservations_rev`` to get the revision timelime.


Example
-------

For the following timeline:

- On 2015-04-02, Steve makes a reservation for party of 6 on 2015-04-15 at 19:30.
- On 2015-04-03, Steve changes the reservation to 4 people.
- On 2015-04-08, Steve cancels the reservation.


``reservations_rev`` will have the following 

===========  ===============  =============  ======  ======  ==========  ======  ======  ==========================
rev_id       rev_created      rev_isdelete   id      name    date        time    party   last_modified
===========  ===============  =============  ======  ======  ==========  ======  ======  ==========================
c74d5bce...  1427995346.0     False          1       Steve   2015-04-15  19:00   6       2015-04-02 13:22:26.291670
f3f5091d...  1428068391.0     False          1       Steve   2015-04-15  19:00   4       2015-04-03 09:39:51.098798
3cf1394b...  1428534191.0     True           1       (null)  (null)      (null)  (null)  (null)
===========  ===============  =============  ======  ======  ==========  ======  ======  ==========================



Design Decisions
----------------

Writing to revision table for all writes
````````````````````````````````````````

There are several advantages by writing to the revision table for all writes:

  1. complete transaction history in the revision table for easy reads (no joins required)
  2. complete timeline even if the original table doesn't have a last modified column


However, this approach has a particular drawback with ``INSERT`` statements with dynamic defaults (such as sequences or auto-datetime). At the time of the insert, the revision table does not have the dynamic values. We recommend the following workarounds:

  1. generate dynamic defaults during object instantiation instead using database defaults
  2. strictly use client-side defaults in the ORM
  3. create server-side database triggers to copy values to revision table for inserts
  4. perform a write-read-write transaction for inserts, which is sub-optimal due to the performance hit


Use of rev_created
``````````````````

To re-create the revision timeline, we are relying on the use of timestamps. While we recognize there could be clock drift or desynchronization across different servers, there are solutions to these problems. Hence we opt to proceed with timestamp's simplicity.


Use of rev_isdelete
```````````````````

The ``rev_isdelete`` is a fast and convenient way to determined that a row has been deleted without inspecting the entries. It also allows for entries with all nulls.


Requirement of primary/compound keys
````````````````````````````````````

TBD


Requirement of association objects for many-to-many relationships
`````````````````````````````````````````````````````````````````

TBD
