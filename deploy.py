import functools
import logging
import os
import posixpath
import time

import typer
from requests.exceptions import HTTPError

from api import NekoWebAPI
from custom_logger import StructuredLogger
from encrypt import compute_md5
from requester import Requester

logging.setLoggerClass(StructuredLogger)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("neko-deploy")


def handle_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            raise
        except Exception as e:
            details = None
            if type(e).__name__ == "HTTPError":
                details = None
                if e.response:
                    details = e.response.text

            logger.error(
                {
                    "message": "One or more errors occurred during deployment",
                    "error": str(e),
                    "details": details,
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


def prune_remote(api, deploy_dir, expected_files, expected_dirs):
    """Remove stale remote files/dirs after a successful upload.

    Never wipes the site: at ``DEPLOY_DIR=/`` only top-level files are pruned
    (directories are protected so migrated multi-site folders survive); under a
    ``/<domain>`` folder the subtree is pruned against the local build.
    """
    protected = {os.path.basename(p) for p in api.get_special_files()} | {"_file_states"}
    files_deleted = 0
    dirs_deleted = 0

    def _delete(path):
        nonlocal files_deleted, dirs_deleted
        try:
            api.delete_file_or_directory(path, ignore_not_found=True)
        except (HTTPError, OSError) as exc:
            logger.debug({"message": "Prune delete failed", "path": path, "error": str(exc)})
            return
        logger.debug({"message": "Pruned stale entry", "path": path})

    if deploy_dir == "/":
        logger.warning(
            {
                "message": "Pruning root deploy dir; only top-level files are removed and "
                "directories are protected. Migrated (multi-site) sites should set DEPLOY_DIR "
                "to their /<domain> folder."
            }
        )
        for item in api.list_files("/"):
            name = item.get("name")
            if not name:
                continue
            if bool(item.get("dir", False)):
                continue  # never delete a root directory (other sites live here)
            if name in protected:
                continue
            full = posixpath.join("/", name)
            if full in expected_files:
                continue
            _delete(full)
            files_deleted += 1
    else:
        for path, is_dir in api.walk_remote(deploy_dir):
            if is_dir:
                if path not in expected_dirs:
                    _delete(path)
                    dirs_deleted += 1
            else:
                if os.path.basename(path) in protected:
                    continue
                if path in expected_files:
                    continue
                _delete(path)
                files_deleted += 1

    logger.info(
        {
            "message": "Pruned stale remote entries",
            "files_deleted": files_deleted,
            "dirs_deleted": dirs_deleted,
        }
    )


def deploy(api, build_dir, deploy_dir, encryption_key, delay=0.5, cleanup=False):
    stats = {
        "message": "Deployed build to NekoWeb",
        "build_dir": build_dir,
        "deploy_dir": deploy_dir,
        "encryption_key": bool(encryption_key),
        "delay": delay,
        "cleanup": cleanup,
        "files_uploaded": 0,
        "files_skipped": 0,
        "files_failed": 0,
        "directories_created": 0,
        "directories_skipped": 0,
        "directories_failed": 0,
    }

    expected_files = set()
    expected_dirs = set()

    file_states = api.fetch_file_states(deploy_dir, encryption_key)
    for root, _, files in os.walk(build_dir):
        relative_path = os.path.relpath(root, build_dir)
        if relative_path == ".":
            server_path = deploy_dir
        else:
            rel_posix = relative_path.replace(os.sep, "/")
            server_path = posixpath.join(deploy_dir, rel_posix)
        expected_dirs.add(server_path)

        try:
            created = api.create_directory(server_path)
        except (HTTPError, OSError) as exc:
            logger.error(
                {"message": "Failed to create directory", "path": server_path, "error": str(exc)}
            )
            stats["directories_failed"] += 1
            created = None

        if created:
            logger.info({"message": "Directory created", "directory": server_path})
            stats["directories_created"] += 1
            time.sleep(delay)
        elif created is False:
            logger.info(
                {
                    "message": "Directory skipped",
                    "directory": server_path,
                    "reason": "Directory already exists",
                }
            )
            stats["directories_skipped"] += 1

        for file in files:
            if file == "_file_states":
                continue

            local_path = os.path.join(root, file)
            server_file_path = posixpath.join(server_path, file)
            expected_files.add(server_file_path)

            try:
                local_md5 = compute_md5(local_path)
                if server_file_path not in file_states or local_md5 != file_states.get(server_file_path):
                    api_method = api.upload_file
                    if os.path.basename(server_file_path) in api.get_special_files():
                        # some files are special and cannot be overwritten/uploaded via upload_file
                        api_method = api.edit_file

                    if api_method(local_path, server_file_path):
                        action = "File uploaded" if server_file_path not in file_states else "File updated"
                        logger.info({"message": action, "file": server_file_path, "reason": "MD5 mismatch"})
                        file_states[server_file_path] = local_md5
                        stats["files_uploaded"] += 1
                        time.sleep(delay)
                    else:
                        logger.error({"message": "Failed to upload file", "file": local_path})
                        stats["files_failed"] += 1
                        time.sleep(delay)
                else:
                    logger.info({"message": "File skipped", "file": local_path, "reason": "MD5 match"})
                    stats["files_skipped"] += 1
            except (HTTPError, OSError) as exc:
                logger.error(
                    {"message": "Failed to upload file", "path": server_file_path, "error": str(exc)}
                )
                stats["files_failed"] += 1
                continue

    file_states_path = os.path.join(build_dir, "_file_states")
    if not api.update_file_states(file_states, file_states_path, deploy_dir, encryption_key):
        logger.error({"message": "Failed to update remote file states", "file": file_states_path})
    else:
        logger.info({"message": "File states updated", "file": file_states_path})

    if cleanup:
        prune_remote(api, deploy_dir, expected_files, expected_dirs)

    logger.info(stats)

    if stats["files_failed"] > 0 or stats["directories_failed"] > 0:
        raise RuntimeError(
            f"Deploy finished with {stats['files_failed']} file and "
            f"{stats['directories_failed']} directory failures; site is partially updated."
        )


@app.command()
@handle_errors
def main(
    api_key: str = typer.Argument(..., help="Your NekoWeb API key for authentication"),
    build_dir: str = typer.Argument(..., help="Directory containing your website build files"),
    deploy_dir: str = typer.Argument(..., help="Directory on NekoWeb to deploy to"),
    cleanup: str = typer.Argument(..., help="Whether to prune stale remote files after deployment"),
    nekoweb_pagename: str = typer.Argument(
        ..., help="Your NekoWeb page name (your username unless you use a custom domain)"
    ),
    delay: float = typer.Option(0.5, help="Delay in seconds between each API call (default is 0.5)"),
    retry_attempts: int = typer.Option(5, help="Number of times to retry a failed API call (default is 5)"),
    retry_delay: float = typer.Option(1.0, help="Delay in seconds between each retry attempt (default is 1.0)"),
    retry_exp_backoff: bool = typer.Option(
        False, help="Whether to use exponential backoff for retry attempts (default is False)"
    ),
    encryption_key: str = typer.Option(
        None, help="A secret key used to encrypt the file states. Must be a 32-byte raw key string"
    ),
    debug: bool = typer.Option(False, help="Whether to enable debug mode and print tracebacks to the console"),
):
    if not os.path.isdir(build_dir) or not os.access(build_dir, os.R_OK):
        logger.error({"message": f"BUILD_DIR does not exist or is not readable: {build_dir}"})
        raise typer.Exit(code=1)
    if encryption_key and len(encryption_key.encode()) != 32:
        logger.error(
            {
                "message": "ENCRYPTION_KEY must be exactly 32 bytes "
                "(the raw key string, not base64)."
            }
        )
        raise typer.Exit(code=1)

    # setup Requester singleton
    Requester(max_retries=retry_attempts, backoff_factor=retry_delay, exponential_backoff=retry_exp_backoff)

    # setup logger and debug
    global DEBUG
    DEBUG = debug
    if DEBUG:
        logger.setLevel(logging.DEBUG)

    # initialize
    base_url = os.environ.get("NEKOWEB_BASE_URL", "nekoweb.org")
    api = NekoWebAPI(api_key, base_url, nekoweb_pagename)

    deploy(api, build_dir, deploy_dir, encryption_key, delay, cleanup=(cleanup.lower() == "true"))


if __name__ == "__main__":
    app()
