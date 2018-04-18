from eve_sqlalchemy.config import DomainConfig, ResourceConfig
import db

import conf

DEBUG = True
SQLALCHEMY_DATABASE_URI = conf.db_driver + '://' + conf.db_user + ':' + conf.db_password + '@' + conf.db_host + '/' + conf.db_name
SQLALCHEMY_TRACK_MODIFICATIONS = False
RESOURCE_METHODS = ['GET', 'POST']

DOMAIN = DomainConfig({
    'poster': ResourceConfig(db.Poster)
}).render()