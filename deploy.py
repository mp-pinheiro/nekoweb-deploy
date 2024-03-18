import os
import sys
import requests

BASE_URL = "https://nekoweb.org/api"
API_KEY = sys.argv[1]
BUILD_DIR = sys.argv[2]
DEPLOY_DIR = sys.argv[3]
CLEANUP = sys.argv[4].lower() == "true"


def delete_file_or_dir(name):
    data = {"pathname": name}
    print(data)
    response = requests.post(
        f"{BASE_URL}/files/delete", headers={"Authorization": API_KEY}, data=data
    )
    if response.status_code != 200:
        print(f"Error deleting {name}: {response.text}")


def create_directory(pathname):
    data = {"isFolder": "true", "pathname": pathname}
    response = requests.post(
        f"{BASE_URL}/files/create", headers={"Authorization": API_KEY}, data=data
    )
    if response.status_code != 200:
        print(f"Can't create directory {pathname}: {response.text}")


def upload_file(filepath, server_path):
    print(f"Uploading {filepath} to {server_path}")
    with open(filepath, "rb") as f:
        files = {"files": (os.path.basename(filepath), f, "application/octet-stream")}
        data = {"pathname": os.path.dirname(server_path)}

        response = requests.post(
            f"{BASE_URL}/files/upload",
            headers={"Authorization": API_KEY},
            # Remove the "Content-Type" header to let requests handle it
            data=data,
            files=files,
        )
        if response.status_code != 200:
            print(f"Error uploading file {filepath}: {response.text}")


def deploy_files_and_directories():
    create_directory(DEPLOY_DIR)
    for root, dirs, files in os.walk(BUILD_DIR):
        relative_path = os.path.relpath(root, BUILD_DIR)
        if relative_path != ".":
            server_path = os.path.join(DEPLOY_DIR, relative_path.replace("\\", "/"))
            create_directory(server_path)
        else:
            server_path = DEPLOY_DIR

        for file in files:
            file_path = os.path.join(root, file)
            server_file_path = os.path.join(server_path, file).replace("\\", "/")
            upload_file(file_path, server_file_path)


if CLEANUP:
    print("Cleaning up files...")
    read_folder_response = requests.get(
        f"{BASE_URL}/files/readfolder?pathname={DEPLOY_DIR}",
        headers={"Authorization": API_KEY},
    )
    if read_folder_response.status_code == 200:
        files_and_dirs = [item["name"] for item in read_folder_response.json()]
        for file_or_dir in files_and_dirs:
            delete_file_or_dir(os.path.join(DEPLOY_DIR, file_or_dir))
    else:
        print(f"Error reading folder: {read_folder_response.text}")

print("Deploying files and directories...")
deploy_files_and_directories()
