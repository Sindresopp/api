import os
import datetime

SECRET_KEY = '_\x0e\x88\x7f\x9ap\x0b\xa8?p\xe9\xa1\xb3\x194\x06!\xde\xe2e-\xf8\x87\xed'
DEBUG = True
DEVELOPMENT = True
JSON_AS_ASCII = False
JSON_SORT_KEYS = False

# Database configuration
MYSQL_DATABASE_USER = 'remoteaccount'
MYSQL_DATABASE_PASSWORD = '3xAchs.6'
MYSQL_DATABASE_DB = 'v2test'
MYSQL_DATABASE_HOST = 'databasenettverket.westeurope.cloudapp.azure.com'

JWT_SECRET_KEY = "t1NP63m4wnBg6nyHYKfmc2TpCOGI4nss"
JWT_ACCESS_TOKEN_EXPIRES = datetime.timedelta(hours=12)
