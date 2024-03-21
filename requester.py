import time
import requests
from requests.exceptions import HTTPError


class Requester:
    def __init__(self, max_retries=5, backoff_factor=0.3):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def request(self, method, url, **kwargs):
        retries = self.max_retries
        ignored_errors = kwargs.pop("ignored_errors", {})

        while retries > 0:
            response = requests.request(method, url, **kwargs)

            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                time.sleep(self.backoff_factor)
                retries -= 1
            else:
                # check if the error is in the ignored_errors dictionary
                if response.status_code in ignored_errors:
                    error = ignored_errors[response.status_code]
                    # check if the error message is the same as the response text
                    if error.get("message") == response.text or error.get("partial_message") in response.text:
                        return response

                # raise an exception if the error is not in the ignored_errors dictionary
                print(response.text)
                response.raise_for_status()

        raise HTTPError(f"Max retries exceeded for URL: {url} ({retries} retries)")
