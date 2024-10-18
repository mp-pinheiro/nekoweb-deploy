import logging
import time

import requests
from requests.exceptions import HTTPError

logger = logging.getLogger("neko-deploy")


class Requester:
    _shared_state = {}

    def __init__(self, max_retries=5, backoff_factor=1, exponential_backoff=False):
        self.__dict__ = self._shared_state
        if not hasattr(self, "max_retries"):
            self.max_retries = max_retries
        if not hasattr(self, "backoff_factor"):
            self.backoff_factor = backoff_factor
        if not hasattr(self, "exponential_backoff"):
            self.exponential_backoff = exponential_backoff

    def request(self, method, url, **kwargs):
        """Make a request to the given URL with the given method and keyword arguments.

        Args:
            method (str): The HTTP method to use for the request.
            url (str): The URL to make the request to.
            ingored_errors (dict): A dictionary of status codes and error messages to ignore.
                {400: {"message": "File/folder already exists"}}
                {404: {"partial_message": "not exist"}}
                {404: {"ignore_all": True}}
            **kwargs: Additional keyword arguments to pass to the requests.request method.

        Returns:
            requests.Response: The response object for the request.

        Raises:
            HTTPError: If the request fails after the maximum number of retries.
        """
        retries = self.max_retries
        ignored_errors = kwargs.pop("ignored_errors", {})
        retry_time = self.backoff_factor

        while retries > 0:
            logger.debug({"message": "Making request", "method": method, "url": url, "retries": retries, **kwargs})
            response = requests.request(method, url, **kwargs)

            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                time.sleep(self.backoff_factor)
                retries -= 1
                if self.exponential_backoff:
                    retry_time *= 2
            else:
                # check if the error is in the ignored_errors dictionary
                if response.status_code in ignored_errors:
                    error = ignored_errors[response.status_code]
                    # check if the error message is the same as the response text
                    if (
                        error.get("ignore_all")
                        or error.get("message") == response.text
                        or error.get("partial_message") in response.text
                    ):
                        return response

                # raise an exception if the error is not in the ignored_errors dictionary
                try:
                    response.raise_for_status()
                except HTTPError as http_err:
                    raise HTTPError(
                        f"HTTP error occurred: {http_err}, Status Code: {response.status_code}, Response Text: {response.text}"  # noqa
                    )

        raise HTTPError(f"Max retries exceeded for URL: {url} ({retries} retries)")
