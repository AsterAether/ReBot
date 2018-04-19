from eve_sqlalchemy.config import DomainConfig, ResourceConfig
import db

import conf

DEBUG = True
URL_PREFIX = 'api'
SQLALCHEMY_DATABASE_URI = conf.db_driver + '://' + conf.db_user + ':' + conf.db_password + '@' + conf.db_host + '/' + conf.db_name
SQLALCHEMY_TRACK_MODIFICATIONS = False
RESOURCE_METHODS = ['GET', 'POST']

DOMAIN = DomainConfig({
    'shop': ResourceConfig(db.Shop),
    'product': ResourceConfig(db.Product)
}).render()

DOMAIN['shop'].update({
    'authorization': None
})

DOMAIN['product'].update({
    'authorization': None
})
