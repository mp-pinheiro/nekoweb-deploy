# Nekoweb Deploy Action
Deploy to nekoweb using a Github action.

# Usage

- Create a `.github/workflows/deploy.yml` file in your repository.
- Add the following code to the `deploy.yml` file.
- Parameters:
  - `API_KEY`: Your Nekoweb API key. It must be stored in the Github repository secrets. Example: `${{ secrets.API_KEY }}`.
  - `BUILD_DIR`: The directory where the build files are located. **Modify the "Prepare build" step to copy the build files to this directory.** Example: `./build`
  - `DEPLOY_DIR`: The directory where the build files will be deployed. Example: if your build files are located in `./build` and you want to deploy them to the root directory, use `/`. If you want to deploy them to a subdirectory, use the subdirectory path. Example: `/subdir`
  - `CLEANUP`: If `True`, the deploy directory will be cleaned up before deploying the build files. **⚠ Use with caution, especially on the root directory. All files in the remote directory (your website) will be deleted.** Example: `True` or `False`.

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
        uses: mp-pinheiro/nekoweb-deploy@latest
        with:
          API_KEY: ${{ secrets.NEKOWEB_API_KEY }}
          BUILD_DIR: './build'
          DEPLOY_DIR: '/'
          CLEANUP: 'False'
```