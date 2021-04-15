from time import time
from contextlib import contextmanager

from peewee import SqliteDatabase, CharField, IntegerField, Model, OperationalError


db = SqliteDatabase('db.db')
_1_DAY = 86400
_3_DAYS = 259200

class Account(Model):
    email = CharField()
    sid = CharField(192)
    change_in = IntegerField()

    class Meta:
        database = db

class Update(Model):
    up_lib_in = IntegerField()
    up_deps_in = IntegerField()

    class Meta:
        database = db


@contextmanager
def query():
    try:
        db.connect()
        yield
    except OperationalError:
        yield
    finally:
        db.close()


class DB:
    def __init__(self):
        Account.create_table()
        Update.create_table()

    def add_account(self, email, sid):
        with query():
            Account(email=email, sid=sid, change_in=int(time())).save()

    def get_account(self, email):
        with query():
            try:
                acc = Account.get(Account.email == email)
                if int(time()) - acc.change_in >= 86400:
                    acc.delete_instance()
                    return None
                return acc.sid
            except Account.DoesNotExist:
                return None
        
    def update_time_of(self, attr):
        with query():
            up = Update.get()
            if attr == 'lib':
                up.up_lib_in = int(time())
            elif attr == 'deps':
                up.up_deps_in = int(time())
            up.save()

    def create_update(self):
        Update(up_lib_in=int(time()), up_deps_in=int(time())).save()

    def lib_need_update(self):
        with query():
            try:
                if int(time()) - Update.get().up_lib_in >= _1_DAY:
                    self.update_time_of('lib')
                    return True
            except Update.DoesNotExist:
                self.create_update()
                return False

    def deps_need_update(self):
        with query():
            if int(time()) - Update.get().up_deps_in >= _3_DAYS:
                self.update_time_of('deps')
                return True
    