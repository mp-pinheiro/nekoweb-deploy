# Nekoweb Deploy Action

Deploy to nekoweb using a Github action.

# About this repository

This action is not officially supported by Nekoweb. It is a community contribution. This version is in a very early stage and may not work as expected.

All logic is contained in the `action.yml` and `deploy.py` files. The `action.yml` file is used to define the inputs and outputs of the action. The `deploy.py` file is used to define the logic of the action.

## Execution flow

1. Once triggered, the python script will check if the required parameters are present.
1. If the `CLEANUP` parameter is `True`, the deploy directory will be cleaned up, that is, **all files in the remote directory (your website) will be deleted**. It does this by retrieving the list of files in the deploy directory using the `files/readfolder` endpoint and deleting them using the `files/delete` endpoint.
1. The script will iterate over the files in the build directory recursively and send them to the Nekoweb API using the `files/upload` endpoint: 
    1. For directories, it will create the directory using the `files/create` endpoint.
    1. For files, it will check for a `file_states` file in the deploy directory and compare the file's hash with the hash in the `file_states` file. If the hashes are the same, the file will not be uploaded. If the hashes are different, the file will be uploaded. If the `file_states` file does not exist, the file will be uploaded. The `NEKOWEB_PAGENAME` parameter is used to fetch the `file_states` file from the deploy directory. 
    1. The `file_states` file can be encrypted by passing an `ENCRYPTION_KEY` parameter. If the `ENCRYPTION_KEY` parameter is set, the `file_states` file will be encrypted using the `cryptography` library. The `file_states` file is used to avoid uploading files that have not changed, which can save time and API requests. 
    1. If a `DELAY` is set, the script will wait for the specified time before sending the next request to the API.

## Limitations

- The action does not support the `files/upload` endpoint for files larger than 100MB. This is a limitation of the Nekoweb API. If you need to upload files larger than 100MB, you will need to use the Nekoweb web interface. The action will not fail, but it will not upload the files larger than 100MB.
- There's no support for the `files/move` endpoint. This means that the action will not move files in the deploy directory. If you need to move files, you will need to use the Nekoweb web interface, or set the `CLEANUP` parameter to `True` which will delete all files in the deploy directory and then upload the build files.
- A simple retry mechanism is implemented for API calls. If the API returns a 429 status code, the action will wait for 0.3 seconds and then retry the request. It'll retry the request 5 times before failing. This is a very simple mechanism and may not be enough to avoid rate limits.
- If the deploy fails, the action will not clean up the deploy directory. This means that if the deploy fails, the deploy directory will be in an inconsistent state. You will need to clean it up manually or set the `CLEANUP` parameter to `True` to clean it up automatically, but be aware that this will delete all files in the deploy directory and will not benefit from the file states logic to avoid uploading files that have not changed.

# Usage

- Create a `.github/workflows/deploy.yml` file in your repository.
- Add the following code to the `deploy.yml` file.
- Parameters:
  - `API_KEY`: Your Nekoweb API key. It must be stored in the [Github repository secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions). Example: `${{ secrets.API_KEY }}`.
  - `BUILD_DIR`: The directory where the build files are located. **Modify the "Prepare build" step to copy the build files to this directory.** Example: `./build`
  - `DEPLOY_DIR`: The directory where the build files will be deployed. Example: if your build files are located in `./build` and you want to deploy them to the root directory, use `/`. If you want to deploy them to a subdirectory, use the subdirectory path. Example: `/subdir`
  - `NEKOWEB_PAGENAME`: Your NekoWeb page name (your username unless you use a custom domain). Example: `fairfruit`
  - `CLEANUP`: If `True`, the deploy directory will be cleaned up before deploying the build files. **⚠ Use with caution, especially on the root directory. All files in the remote directory (your website) will be deleted.** This argument is optional and defaults to `False`.
  - `DELAY`: The delay between requests to the Nekoweb API. This is useful to avoid rate limits. Example: `0.5` (half a second). This argument is optional and defaults to `0.5`.
  - `ENCRYPTION_KEY`: A secret key used to encrypt the file states. Must be a 32-byte URL-safe base64-encoded string. You should also store this key in the [Github repository secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions). Example: `${{ secrets.ENCRYPTION_KEY }}`. This argument is optional and no encryption will be used. **That means the file states will be stored in plain text in the deploy directory containing a list of all files and their hashes from your build directory. Use with caution.**

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
        uses: mp-pinheiro/nekoweb-deploy@0.2.2
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

# Using it locally

You can use the action locally using the `deploy.py` script. You will need to install the dependencies using `pip install -r requirements.txt`. Then you can run the script using the following command:

```bash
python deploy.py [--debug] \
  [--delay <DELAY>]
  [--encryption-key <ENCRYPTION_KEY>] \
  <API_KEY> \
  <BUILD_DIR> \
  <DEPLOY_DIR> \
  <CLEANUP> \
  <NEKOWEB_PAGENAME>
```

# Contributing

This action is in a very early stage and may not work as expected. If you find any issues, please open an issue or a pull request. All contributions are welcome. 

Here are some ideas for contributions:

- There's still room for improvements in the code. The code is not very clean and could be better organized.
- Add a more robust and configurable retry mechanism for API calls.
- Add support for deleting/renaming/moving files (besides the `CLEANUP` parameter)
- Add support for files larger than 100MB using the `bigfiles` endpoints
- Using `typer` for the CLI might conflict with the `handle_errors` decorator.
