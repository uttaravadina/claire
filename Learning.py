import configparser
import logging
import couchdb

from lib.HomeState import HomeState
from lib.NetworkService import NetworkService

config = configparser.ConfigParser()
config.read('config.cfg')

if not "General" in config.sections():
    print("Missing general section in configuration file. Please check config.cfg exists.")
    exit()

# Configuration
home_name = config.get("General", "home_name")

couchdb_server = config.get("CouchDB", "url")
couchdb_name = config.get("CouchDB", "db")

logfile = config.get("Log","logfile")
ouput_log_to_console = config.getboolean("Log","ouput_log_to_console")

# Connect to CouchDB
couch = couchdb.Server(couchdb_server)

try:
    couchdb = couch[couchdb_name]
except couchdb.http.ResourceNotFound:
    print("Error database $(couchdb_name)s does not exist")

home_states = HomeState.view(couchdb, "_design/home_state/_view/by_time")

for home in home_states:
    print(home.time)
    print(home.feature_vector())
    print(home.output_vector())
