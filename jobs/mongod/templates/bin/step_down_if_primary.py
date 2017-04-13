#!/usr/bin/env python

<% if p('mongod.arbiter') %>

# arbiter node
print(0)

<% else %>

# data bearing node
# inspired by: https://github.com/mongodb/mongo-python-driver/blob/master/test/high_availability/ha_tools.py

import logging
import time
import pymongo
import pymongo.errors
from pymongo import MongoClient

host = "127.0.0.1:<%= p('mongod.port') %>"
user = "<%= p("mongod.admin_user") %>"
password = "<%= p("mongod.admin_password") %>"
log_file = "/var/vcap/sys/log/mongod/drain.log"

logger = logging.getLogger('mongo_drain')
handler = logging.FileHandler(log_file)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

def get_client():
    client = MongoClient(host)
    client.admin.authenticate(user, password)
    # force connection
    client.admin.command("isMaster")
    return client

def stepdown_primary():
    client = get_client()
    logger.info('Stepping down primary')

    for _ in range(10):
        try:
            client.admin.command('replSetStepDown', 20)
        except pymongo.errors.OperationFailure as exc:
            logger.info('\tCode %s from replSetStepDown: %s' % (exc.code, exc))
            logger.info('\tTrying again in one second....')

            time.sleep(1)
        except pymongo.errors.ConnectionFailure as exc:
            # replSetStepDown causes mongod to close all connections.
            logger.info('\tException from replSetStepDown: %s' % exc)

            # Seems to have succeeded.
            break
    else:
        logger.error("Couldn't complete replSetStepDown")
        raise AssertionError("Couldn't complete replSetStepDown")

    logger.info('\tcalled replSetStepDown')

def get_members_in_state(state):
    status = get_client().admin.command('replSetGetStatus')
    members = status['members']
    return [k['name'] for k in members if k['state'] == state]

def get_primary():
    try:
        primaries = get_members_in_state(1)
        assert len(primaries) <= 1
        if primaries:
            return primaries[0]
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        pass

    return None

def wait_for_primary():
    logger.info("Waiting for primary")
    for _ in range(30):
        time.sleep(1)
        if get_primary():
            logger.info("\tprimary is up!!!")
            break
    else:
        logger.error("Primary didn't come back up!!!")
        raise AssertionError("Primary didn't come back up!!!")

#######################
# step down if primary
#######################
c = get_client()
res = c.admin.command("isMaster")

logger.info("me: %s" % res['me'])
logger.info("ismaster: %s" % res['ismaster'])
logger.info("secondary: %s" % res['secondary'])

if res['ismaster']:
    stepdown_primary()
    wait_for_primary()
else:
    logger.info("Not a master, safe to shut down...")

print(0)

<% end %>

