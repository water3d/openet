import logging

import requests
import json

logging.basicConfig()

from . import raster
from .raster import RasterManager
from .geodatabase import Geodatabase
from .exceptions import AuthenticationError, RateLimitError
from .cache import Cacher


class OpenETClient(object):
    token = None
    _base_url = "https://openet.dri.edu/"
    _validate_ssl = False

    def __init__(self, token=None):
        self.token = token
        self.raster = RasterManager(client=self)
        self.geodatabase = Geodatabase(client=self)
        self.cache = Cacher()
        self._last_request = None  # just for debugging

    def _check_token(self):
        if self.token is None:
            raise AuthenticationError("Token missing/undefined - you must set the value of your token before proceeding")

    def send_request(self, endpoint, method="get", disable_encoding=False, **kwargs):
        """
            Handles sending most requests to the API - they provide the endpoint and the args.
            Since the API is in the process of switching from GET to POST requests, we have logic that switches between
            those depending on the request method
        :param endpoint: The text path to the OpenET endpoint - e.g. raster/export - skip the base URL.
        :param method: "get" or "post" (case sensitive) - should match what the API supports for the endpoint
        :param kwargs: The arguments to send (via get or post) to the API
        :return: requests.Response object of the results.
        """

        self._check_token()

        requester = getattr(requests, method)
        send_kwargs = kwargs
        # they're not currently switching between post args and get args - it's just a get request that we POST instead...
        # send_kwargs = {}
        #if method == "get":
        #    send_kwargs["params"] = kwargs
        #    send_kwargs["data"] = None
        #elif method == "post":
        #    send_kwargs["data"] = kwargs
        #    send_kwargs["params"] = None

        url = self._base_url + endpoint
        logging.info(f"Connecting to {url}")
        logging.info(f"Sending params {kwargs}")
        logging.info(f"Sending token in header{self.token}")

        extra_kwargs = {}
        if self._validate_ssl != True:
            extra_kwargs['verify'] = False

        if disable_encoding and method == "get":  # the API doesn't always like certain things URL-encoded, so don't
            send_kwargs = "&".join("%s=%s" % (k, v) for k, v in send_kwargs.items())

        if method == "post":
            body = json.dumps(send_kwargs)
            result = requester(url, headers={"Authorization": self.token}, data=body, **extra_kwargs)
        else:
            body = send_kwargs
            result = requester(url, headers={"Authorization": self.token}, params=body, **extra_kwargs)
        self._last_request = result

        # cache the request and response so that if anything goes wrong, we've saved the data
        self.cache.cache_request(url, body, result.status_code, json.dumps(result.json()))

        if result.status_code in (500, 404) and "reached your maximum rate limit" in result.json()["description"]:
            raise RateLimitError("Server indicates we've reached our rate limit - try increasing the wait time between requests")

        return result
