from __future__ import absolute_import
from google.appengine.ext import ndb
import hashlib
import endpoints
import os
from oauth2client.client import AccessTokenCredentials


def get_endpoints_credentials():
    """
    Gets the oauth2 credentials from the user authenticated to Google Cloud Endpoints.

    Presently, this does not work for Android and iOS clients. We are open to patches to fix it.
    """
    user = endpoints.get_current_user()
    if not user:
        return False

    if not 'HTTP_AUTHORIZATION' in os.environ:
        return False

    token = os.environ['HTTP_AUTHORIZATION'].split(' ').pop()
    credentials = AccessTokenCredentials(token, 'appengine:ferris')

    return credentials


def _get_config():
    from . import settings
    config = settings.get('oauth2_service_account')
    if not config:
        raise RuntimeError("OAuth2 Service Account is not configured correctly")
    return config


try:
    from oauth2client.client import SignedJwtAssertionCredentials
except ImportError:
    SignedJwtAssertionCredentials = None

from oauth2client.appengine import StorageByKeyName, CredentialsNDBProperty


def build_service_account_credentials(scope, user=None):
    """
    Builds service account credentials using the configuration stored in :mod:`~ferris3.settings`
    and masquerading as the provided user.
    """
    if not SignedJwtAssertionCredentials:
        raise EnvironmentError("Service account can not be used because PyCrypto is not available. Please install PyCrypto.")

    config = _get_config()

    if not isinstance(scope, (list, tuple)):
        scope = [scope]

    key = _generate_storage_key(config['client_email'], scope, user)
    storage = StorageByKeyName(ServiceAccountStorage, key, 'credentials')

    creds = SignedJwtAssertionCredentials(
        service_account_name=config['client_email'],
        private_key=config['private_key'],
        scope=scope,
        prn=user)
    creds.set_store(storage)

    return creds


class ServiceAccountStorage(ndb.Model):
    """
    Tracks access tokens in the database. The key is
    based on the scopes, user, and clientid
    """
    credentials = CredentialsNDBProperty()

    @classmethod
    def _get_kind(cls):
        return '_ferris_OAuth2ServiceAccountStorage'


def _generate_storage_key(client_id, scopes, user):
    s = u"%s%s%s" % (client_id, sorted(scopes), user)
    hash = hashlib.sha1(s.encode())
    return hash.hexdigest()
