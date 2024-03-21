import os
import json

from encrypt import encrypt_data, decrypt_data
from requester import Requester


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

    def list_files(self, pathname):
        response = self.requester.request(
            "GET",
            f"{self.base_url}/files/readfolder?pathname={pathname}",
            headers={"Authorization": self.api_key},
        )
        return response.json() if response.ok else []

    def delete_file_or_directory(self, pathname):
        data = {"pathname": pathname}
        response = self.requester.request(
            "POST",
            f"{self.base_url}/files/delete",
            headers={"Authorization": self.api_key},
            data=data,
        )
        return response.ok

    def fetch_file_states(self, deploy_dir, encryption_key=None):
        file_states_url = f"{self.page_url}/{deploy_dir}/_file_states"
        response = self.requester.request(
            "GET",
            file_states_url,
            headers={"Authorization": self.api_key},
            ignored_errors={404: {"partial_message": "Page was not found."}},
        )

        if response.ok:
            if encryption_key:
                return json.loads(decrypt_data(response.content, encryption_key))
            return response.json()
        else:
            return {}

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
