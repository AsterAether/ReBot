from eve_sqlalchemy.config import DomainConfig, ResourceConfig
import db

import conf

DEBUG = True
URL_PREFIX = 'api'
SQLALCHEMY_DATABASE_URI = conf.db_driver + '://' + conf.db_user + ':' + conf.db_password + '@' + conf.db_host + '/' + conf.db_name
SQLALCHEMY_TRACK_MODIFICATIONS = False
RESOURCE_METHODS = ['GET', 'POST']

DOMAIN = DomainConfig({
    'poster': ResourceConfig(db.Poster),
    'shop': ResourceConfig(db.Shop),
    'product': ResourceConfig(db.Product)
}).render()

DOMAIN['poster'].update({
    'resource_methods': []
})

DOMAIN['shop'].update({
    'authentication': None,
})

DOMAIN['product'].update({
    'authentication': None
})
