# Nekoweb Deploy Action

Deploy to nekoweb using a Github action.

# About this repository

This action is not officially supported by Nekoweb. It is a community contribution. This version is in a very early stage and may not work as expected.

All logic is contained in the `action.yml` and `deploy.py` files. The `action.yml` file is used to define the inputs and outputs of the action. The `deploy.py` file is used to define the logic of the action.

## Execution flow

1. Once triggered, the python script will check if the required parameters are present.
2. If the `CLEANUP` parameter is `True`, the deploy directory will be cleaned up, that is, **all files in the remote directory (your website) will be deleted**. It does this by retrieving the list of files in the deploy directory using the `files/readfolder` endpoint and deleting them using the `files/delete` endpoint.
3. The script will iterate over the files in the build directory recursively and send them to the Nekoweb API using the `files/upload` endpoint. For directories, it will create the directory using the `files/create` endpoint and then upload the files inside the directory. If the deploy directory does not exist, it will be created as well. If a `DELAY` is set, the script will wait for the specified time before sending the next request to the API.

## Limitations

- The action does not support the `files/upload` endpoint for files larger than 100MB. This is a limitation of the Nekoweb API. If you need to upload files larger than 100MB, you will need to use the Nekoweb web interface. The action will not fail, but it will not upload the files larger than 100MB.
- There's no support for the `files/move` endpoint. This means that the action will not move files in the deploy directory. If you need to move files, you will need to use the Nekoweb web interface, or set the `CLEANUP` parameter to `True` which will delete all files in the deploy directory and then upload the build files.
- There are no disaster recovery mechanisms. If the action fails, it will not attempt to recover. If the action fails, you will need to manually recover the deploy directory using the Nekoweb web interface.
- The action will always expect the API to respond with a 200 status code. No error handling is implemented. This is very important to note given the API has rate limits, especially to non-paying users. If any of the API requests fail, a manual recovery will be necessary.

# Usage

- Create a `.github/workflows/deploy.yml` file in your repository.
- Add the following code to the `deploy.yml` file.
- Parameters:
  - `API_KEY`: Your Nekoweb API key. It must be stored in the [Github repository secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions). Example: `${{ secrets.API_KEY }}`.
  - `BUILD_DIR`: The directory where the build files are located. **Modify the "Prepare build" step to copy the build files to this directory.** Example: `./build`
  - `DEPLOY_DIR`: The directory where the build files will be deployed. Example: if your build files are located in `./build` and you want to deploy them to the root directory, use `/`. If you want to deploy them to a subdirectory, use the subdirectory path. Example: `/subdir`
  - `CLEANUP`: If `True`, the deploy directory will be cleaned up before deploying the build files. **⚠ Use with caution, especially on the root directory. All files in the remote directory (your website) will be deleted.** Example: `True` or `False`.
  - `DELAY`: The delay between requests to the Nekoweb API. This is useful to avoid rate limits. Example: `0.5` (half a second). This argument is optional and defaults to `0.5`.

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
        uses: mp-pinheiro/nekoweb-deploy@0.0.2
        with:
          API_KEY: ${{ secrets.NEKOWEB_API_KEY }}
          BUILD_DIR: './build'
          DEPLOY_DIR: '/'
          CLEANUP: 'False'
          DELAY: '0.5'
```

Here's a working example in a Nekoweb website repository: https://github.com/mp-pinheiro/nekoweb-api-docs/blob/main/.github/workflows/main.yml

# Contributing

This action is in a very early stage and may not work as expected. If you find any issues, please open an issue or a pull request. All contributions are welcome. 

Here are some ideas for contributions:

- Add error handling and disaster recovery mechanisms such as retrying failed requests
- Add support for files larger than 100MB using the `bigfiles` endpoints
- Improve logging and error messages
