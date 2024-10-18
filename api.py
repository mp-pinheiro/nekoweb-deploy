import json
import logging
import os

from requests.exceptions import HTTPError

from encrypt import decrypt_data, encrypt_data
from requester import Requester

logger = logging.getLogger("neko-deploy")

# constants
NEKOWEB_API_SPECIAL_FILES = ["/elements.css", "/not_found.html", "/cursor.png"]


class NekoWebAPI:
    def __init__(self, api_key, base_url, page_name):
        self.api_key = api_key
        self.base_url = f"https://{base_url}/api"
        self.page_url = f"https://{page_name}.{base_url}"
        self.requester = Requester()

    def create_directory(self, pathname):
        data = {"isFolder": "true", "pathname": pathname}
        response = self.requester.request(
            "POST",
            f"{self.base_url}/files/create",
            headers={"Authorization": self.api_key},
            data=data,
            ignored_errors={400: {"message": "File/folder already exists"}},
        )
        return response.ok

    def upload_file(self, filepath, server_path):
        with open(filepath, "rb") as f:
            files = {"files": (os.path.basename(filepath), f, "application/octet-stream")}
            data = {"pathname": os.path.dirname(server_path)}
            response = self.requester.request(
                "POST",
                f"{self.base_url}/files/upload",
                headers={"Authorization": self.api_key},
                data=data,
                files=files,
            )
            return response.ok

    def edit_file(self, filepath, server_path):
        with open(filepath, "r") as f:
            files = {"pathname": (None, server_path), "content": (None, f.read())}
            response = self.requester.request(
                "POST", f"{self.base_url}/files/edit", headers={"Authorization": self.api_key}, files=files
            )
            return response.ok

    def list_files(self, pathname):
        try:
            response = self.requester.request(
                "GET",
                f"{self.base_url}/files/readfolder?pathname={pathname}",
                headers={"Authorization": self.api_key},
            )
        except HTTPError:
            return []

        return response.json() if response.ok else []

    def delete_file_or_directory(self, pathname, ignore_not_found=False):
        data = {"pathname": pathname}

        ignored = {}
        if ignore_not_found:
            ignored = {400: {"message": "File/folder does not exist"}}

        response = self.requester.request(
            "POST",
            f"{self.base_url}/files/delete",
            headers={"Authorization": self.api_key},
            data=data,
            ignored_errors=ignored,
        )
        return response.ok

    def fetch_file_states(self, deploy_dir, encryption_key=None):
        # validate page url
        try:
            response = self.requester.request(
                "GET",
                self.page_url,
            )
        except HTTPError:
            logger.warning(
                {
                    "message": f"Could not validate URL: `{self.page_url}`, a full deployment will be performed. "
                    "Check your `NEKOWEB_PAGENAME` parameter.",
                    "url": self.page_url,
                }
            )
            return {}

        # fetch the file states
        file_states_url = f"{self.page_url}/{deploy_dir}/_file_states"
        response = self.requester.request(
            "GET",
            file_states_url,
            headers={"Authorization": self.api_key},
            ignored_errors={404: {"ignore_all": True}},
        )

        if not response.ok:
            return {}

        if encryption_key:
            return json.loads(decrypt_data(response.content, encryption_key))

        try:
            return response.json()
        except json.JSONDecodeError:
            raise ValueError(
                "Invalid encryption key provided. Please provide the correct key or do a fresh deployment."
            )

    def update_file_states(self, file_states, file_states_path, deploy_dir, encryption_key=None):
        file_states_json = json.dumps(file_states)

        if encryption_key:
            encrypted_file_states = encrypt_data(file_states_json, encryption_key)
            with open(file_states_path, "wb") as f:
                f.write(encrypted_file_states)
        else:
            with open(file_states_path, "w") as f:
                f.write(file_states_json)

        return self.upload_file(file_states_path, f"{deploy_dir}/_file_states")

    def get_special_files(self):
        """Return a list of special Nekoweb files that cannot be deleted."""
        return NEKOWEB_API_SPECIAL_FILES
