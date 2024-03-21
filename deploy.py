import functools
import logging
import os
import time

import typer

from api import NekoWebAPI
from custom_logger import StructuredLogger
from encrypt import compute_md5

logging.setLoggerClass(StructuredLogger)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def handle_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(
                {
                    "message": "One or more errors occurred during deployment",
                    "error": str(e),
                    "advice": (
                        "Please check NekoWeb as the state of the website might be corrupted. "
                        "Consider downloading the build artifact and manually uploading the zip file as a workaround. "
                        "You can also open an issue on the `mp-pinheiro/nekoweb-deploy` Github repository if needed."
                    ),
                }
            )

            if DEBUG:
                raise e
            else:
                exit(1)

    return wrapper


app = typer.Typer()


def cleanup_remote_directory(api, deploy_dir):
    logger.info({"message": "Cleaning up the server directory", "directory": deploy_dir})
    items = api.list_files(deploy_dir)
    for item in items:
        full_path = os.path.join(deploy_dir, item["name"])
        logger.info({"message": "Deleting file", "file": full_path})
        if not api.delete_file_or_directory(full_path):
            logger.error({"message": "Failed to delete file", "file": full_path})


def deploy(api, build_dir, deploy_dir, delay, encryption_key, debug):
    stats = {
        "message": "Deployed build to NekoWeb",
        "build_dir": build_dir,
        "deploy_dir": deploy_dir,
        "delay": delay,
        "encryption_key": bool(encryption_key),
        "files_uploaded": 0,
        "files_skipped": 0,
        "directories_created": 0,
        "directories_skipped": 0,
        "debug": debug,
    }

    file_states = api.fetch_file_states(deploy_dir, encryption_key)
    for root, dirs, files in os.walk(build_dir):
        relative_path = os.path.relpath(root, build_dir)
        server_path = deploy_dir if relative_path == "." else os.path.join(deploy_dir, relative_path.replace("\\", "/"))
        if api.create_directory(server_path):
            logger.info({"message": "Directory created", "directory": server_path})
            stats["directories_created"] += 1
        else:
            logger.info(
                {
                    "message": "Directory skipped",
                    "directory": server_path,
                    "reason": "Directory already exists",
                }
            )
            stats["directories_skipped"] += 1
        time.sleep(delay)

        for file in files:
            if file == "_file_states":
                continue
            local_path = os.path.join(root, file)
            server_file_path = os.path.join(server_path, file)
            local_md5 = compute_md5(local_path)

            if server_file_path not in file_states or local_md5 != file_states.get(server_file_path):
                if api.upload_file(local_path, server_file_path):
                    action = "File uploaded" if server_file_path not in file_states else "File updated"
                    logger.info(
                        {
                            "message": action,
                            "file": server_file_path,
                            "reason": "MD5 mismatch",
                        }
                    )
                    file_states[server_file_path] = local_md5
                    stats["files_uploaded"] += 1
                else:
                    logger.error({"message": "Failed to upload file", "file": local_path})
            else:
                logger.info(
                    {
                        "message": "File skipped",
                        "file": local_path,
                        "reason": "MD5 match",
                    }
                )
                stats["files_skipped"] += 1
            time.sleep(delay)

    file_states_path = os.path.join(build_dir, "_file_states")
    if not api.update_file_states(file_states, file_states_path, deploy_dir, encryption_key):
        logger.error({"message": "Failed to update remote file states", "file": file_states_path})
    else:
        logger.info({"message": "File states updated", "file": file_states_path})

    logger.info(stats)


@app.command()
@handle_errors
def main(
    api_key: str = typer.Argument(..., help="Your NekoWeb API key for authentication"),
    build_dir: str = typer.Argument(..., help="Directory containing your website build files"),
    deploy_dir: str = typer.Argument(..., help="Directory on NekoWeb to deploy to"),
    cleanup: str = typer.Argument(..., help="Whether to clean up the deploy directory before deployment"),
    nekoweb_pagename: str = typer.Argument(
        ..., help="Your NekoWeb page name (your username unless you use a custom domain)"
    ),
    delay: float = typer.Option(0.0, help="Delay in seconds between each API call (default is 0.0)"),
    encryption_key: str = typer.Option(
        None, help="A secret key used to encrypt the file states. Must be a 32-byte URL-safe base64-encoded string"
    ),
    debug: bool = typer.Option(False, help="Whether to enable debug mode and print tracebacks to the console"),
):
    global DEBUG
    DEBUG = debug
    api = NekoWebAPI(api_key, "nekoweb.org", nekoweb_pagename)
    if cleanup.lower() == "true":
        cleanup_remote_directory(api, deploy_dir)
    deploy(api, build_dir, deploy_dir, delay, encryption_key, debug)


if __name__ == "__main__":
    app()
