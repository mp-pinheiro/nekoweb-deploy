# Nekoweb Deploy Action

Deploy to nekoweb using a Github action.

# About this repository

This action is not officially supported by Nekoweb. It is a community contribution. This version is in a very early stage and may not work as expected.

All logic is contained in the `action.yml` and `deploy.py` files. The `action.yml` file is used to define the inputs and outputs of the action. The `deploy.py` file is used to define the logic of the action.

## Execution flow

1. Once triggered, the python script will check that the required parameters are present and that `BUILD_DIR` exists and is readable. It also validates the `ENCRYPTION_KEY` length if one is supplied.
1. The script fetches the remote `file_states` file from the deploy directory (if present) so it can skip unchanged files.
1. The script iterates over the files in the build directory recursively and sends them to the Nekoweb API:
    1. For directories, it creates the directory using the `files/create` endpoint.
    1. For files, it compares the file's hash with the hash stored in `file_states`. If the hashes match, the file is skipped. Otherwise the file is uploaded. `NEKOWEB_PAGENAME` is used to fetch the `file_states` file from the deploy directory.
    1. The `file_states` file can be encrypted by passing an `ENCRYPTION_KEY`. When set, `file_states` is encrypted with the `cryptography` library. This avoids uploading unchanged files and saves time and API requests.
1. If `CLEANUP` is `True`, stale remote files are pruned **after** the upload completes (see [CLEANUP](#cleanup) below).

## Limitations

- The action does not support the `files/upload` endpoint for files larger than 100MB. This is a limitation of the Nekoweb API. If you need to upload files larger than 100MB, you will need to use the Nekoweb web interface. The action will not fail, but it will not upload the files larger than 100MB.
- There's no support for the `files/move` endpoint. If you need to move files, you will need to use the Nekoweb web interface, or set `CLEANUP` to `True` so stale files are pruned after the upload.
- A robust retry mechanism is implemented for API calls. Transient statuses (`408`, `429`, and `5xx`) and network errors are retried with backoff. On `429` responses the action honors the NekoWeb `ratelimit-reset` header (capped at 60s per wait), and exponential backoff is available via `RETRY_EXP_BACKOFF`. Permanent `4xx` errors are not retried.
- A single failed upload no longer aborts the whole deploy. Failures are logged and counted, the remaining files are uploaded, and the action exits non-zero at the end so CI fails visibly. The site is never left empty: cleanup prunes stale files only **after** a successful upload, scoped to `DEPLOY_DIR`.

## CLEANUP

When `CLEANUP=True`, stale remote files are removed **after** the upload finishes, scoped to `DEPLOY_DIR`. The upload and `file_states` update always run first, so a mid-deploy failure never wipes the site.

- With `DEPLOY_DIR` set to a domain folder (e.g. `/<domain>`), the entire subtree is pruned against the local build — stale files and empty directories are removed recursively.
- With `DEPLOY_DIR=/` (legacy root), **only top-level files are ever removed**; directories are protected so other sites' domain folders are never touched. Migrated (multi-site) accounts should set `DEPLOY_DIR` to their domain folder instead.
- `elements.css`, `not_found.html`, `cursor.png`, and `_file_states` are always preserved.

## Multi-site routing

NekoWeb routes each site under its own `/<domain>` folder. This action supports both layouts:

- **Migrated sites** (multi-site): set `DEPLOY_DIR` to the domain folder, e.g. `/fairfruit.nekoweb.org`. The full subtree is deployed and pruned there.
- **Legacy sites** (single site): keep `DEPLOY_DIR=/`. Only top-level files are pruned on `CLEANUP`.

Note: `cursor.png` stays at the account root, while `elements.css` and `not_found.html` move into the domain folder. The action matches these special files by basename, so they are handled correctly under either layout.

# Usage

- Create a `.github/workflows/deploy.yml` file in your repository.
- Add the following code to the `deploy.yml` file.
- Parameters:
  - `API_KEY`: Your Nekoweb API key. It must be stored in the [Github repository secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions). Example: `${{ secrets.API_KEY }}`.
  - `BUILD_DIR`: The directory where the build files are located. **Modify the "Prepare build" step to copy the build files to this directory.** Example: `./build`
  - `DEPLOY_DIR`: The directory where the build files will be deployed. Example: if your build files are located in `./build` and you want to deploy them to the root directory, use `/`. For a migrated multi-site account, use the domain folder, e.g. `/fairfruit.nekoweb.org`.
  - `NEKOWEB_PAGENAME`: Your NekoWeb page name (your username unless you use a custom domain). Example: `fairfruit`
  - `CLEANUP`: If `True`, stale remote files are pruned **after** the upload, scoped to `DEPLOY_DIR` (see [CLEANUP](#cleanup)). This argument is optional and defaults to `False`.
  - `DELAY`: The delay between requests to the Nekoweb API. This is useful to avoid rate limits. Example: `0.5` (half a second). This argument is optional and defaults to `0.5`.
  - `RETRY_ATTEMPTS`: The number of retry attempts for transient API errors (429/5xx/network). This argument is optional and defaults to `5`.
  - `RETRY_DELAY`: The base delay between retry attempts in seconds. This argument is optional and defaults to `1`.
  - `RETRY_EXP_BACKOFF`: If `True`, the delay between retry attempts uses exponential backoff. This argument is optional and defaults to `False`.
  - `ENCRYPTION_KEY`: A secret key used to encrypt the file states. Must be a **32-byte raw key string** (Fernet derives the URL-safe base64 key internally). You should also store this key in the [Github repository secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions). Example: `${{ secrets.ENCRYPTION_KEY }}`. This argument is optional and no encryption will be used. **That means the file states will be stored in plain text in the deploy directory containing a list of all files and their hashes from your build directory. Use with caution.**

> **Pin to a tag, not `@main`.** The action is released via git semver tags. `@main` is the active development line and may include breaking changes. Pin to a tag for reproducible deploys.

```yaml
name: Deploy to Nekoweb

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Prepare build
        run: |
          mkdir -p ./build
          cp -r ./public/* ./build

      - name: Deploy to Nekoweb
        uses: mp-pinheiro/nekoweb-deploy@0.3.0
        with:
          API_KEY: ${{ secrets.NEKOWEB_API_KEY }}
          BUILD_DIR: './build'
          DEPLOY_DIR: '/'
          CLEANUP: 'False'
          DELAY: '0.5'
          NEKOWEB_PAGENAME: 'fairfruit'
          ENCRYPTION_KEY: ${{ secrets.NEKOWEB_ENCRYPTION_KEY }}
```

Here's a working example in a Nekoweb website repository: https://github.com/mp-pinheiro/nekoweb-api-docs/blob/main/.github/workflows/main.yml

# Versioning

This action is versioned with git tags (`0.0.1` … `0.3.0`).

- `@0.3.0` is the hardened release: prune-after cleanup (never wipes the site), basename special-files matching (works for both legacy and multi-site routing), rate-limit-aware retries, continue-on-error uploads, and safe action inputs.
- `@0.2.9` is the last **legacy** release (pre-prune cleanup, root-absolute special-files matching) for non-migrated sites that depend on the older behavior.

Pin to a specific tag rather than `@main`.

# Using it locally

You can use the action locally using the `deploy.py` script. You will need to install the dependencies using `pip install -r requirements.txt`. Then you can run the script using the following command:

```bash
python deploy.py \
  [--delay <DELAY>] \
  [--retry-attempts <RETRY_ATTEMPTS>] \
  [--retry-delay <RETRY_DELAY>] \
  [--retry-exp-backoff] \
  [--encryption-key <ENCRYPTION_KEY>] \
  [--debug] \
  <API_KEY> \
  <BUILD_DIR> \
  <DEPLOY_DIR> \
  <CLEANUP> \
  <NEKOWEB_PAGENAME>
```

For local/mock testing you can override the NekoWeb host with the `NEKOWEB_BASE_URL` environment variable, e.g. `export NEKOWEB_BASE_URL=http://localhost:8765` to point the API client at a local server.

# Contributing

This action is in a very early stage and may not work as expected. If you find any issues, please open an issue or a pull request. All contributions are welcome.

Here are some ideas for contributions:

- There's still room for improvements in the code. The code is not very clean and could be better organized.
- Add support for deleting/renaming/moving files (besides the `CLEANUP` parameter)
- Add support for files larger than 100MB using the `bigfiles` endpoints
