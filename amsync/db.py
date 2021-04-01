from time import time
from contextlib import contextmanager

from peewee import SqliteDatabase, CharField, IntegerField, Model


db = SqliteDatabase('db.db')


class Account(Model):
    email = CharField()
    sid = CharField(192)
    timestamp = IntegerField()

    class Meta:
        database = db


@contextmanager
def query():
    db.connect()
    yield
    db.close()


class DB:
    def __init__(self):
        Account.create_table()

    def add(self, email, sid):
        with query():
            Account(email=email, sid=sid, timestamp=int(time())).save()

    def get(self, email):
        with query():
            try:
                acc = Account.get(Account.email == email)
                if int(time()) - acc.timestamp >= 86400:
                    acc.delete_instance()
                    return None

                return acc.sid
            except Account.DoesNotExist:
                return None
