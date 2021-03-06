import hashlib
import hmac
import urlparse

from baseplate import config
from twisted.web import resource, server
from twisted.application import internet
from twisted.internet import reactor
from twisted.internet.endpoints import serverFromString

from harold.utils import constant_time_compare


class HttpPlugin(object):
    def __init__(self, root, hmac_secret):
        self.root = root
        self.hmac_secret = hmac_secret


class AuthenticationError(Exception):
    pass


class ProtectedResource(resource.Resource):
    def __init__(self, http):
        self.http = http

    def _authenticate_request(self, request):
        HEADER_NAME = "X-Hub-Signature"
        has_signature = request.requestHeaders.hasHeader(HEADER_NAME)
        if self.http.hmac_secret and has_signature:
            # modern method: hmac of request body
            body = request.content.read()
            expected_hash = hmac.new(
                self.http.hmac_secret, body, hashlib.sha1).hexdigest()

            header = request.requestHeaders.getRawHeaders(HEADER_NAME)[0]
            hashes = urlparse.parse_qs(header)
            actual_hash = hashes["sha1"][0]

            if not constant_time_compare(expected_hash, actual_hash):
                raise AuthenticationError
        else:
            # no further authentication methods
            raise AuthenticationError

    def render_GET(self, request):
        try:
            self._authenticate_request(request)
        except AuthenticationError:
            request.setResponseCode(403)
        else:
            response = self._handle_request(request)

        return response or ""

    def render_POST(self, request):
        try:
            self._authenticate_request(request)
        except AuthenticationError:
            request.setResponseCode(403)
        else:
            response = self._handle_request(request)

        return response or ""


def make_plugin(application, app_config):
    http_config = config.parse_config(app_config, {
        "endpoint": config.String,
        "hmac_secret": config.String,
    })

    root = resource.Resource()
    harold = resource.Resource()
    root.putChild('harold', harold)
    site = server.Site(root)
    site.noisy = False
    site.displayTracebacks = False

    endpoint = serverFromString(reactor, http_config.endpoint)
    service = internet.StreamServerEndpointService(endpoint, site)
    service.setServiceParent(application)

    return HttpPlugin(harold, http_config.hmac_secret)
