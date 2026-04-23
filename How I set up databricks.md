Tutorial from databricks found here: https://docs.databricks.com/aws/en/dev-tools/databricks-apps/tutorial-streamlit

First, I clicked the New button on databricks then I added an app:

!('/Users/hayden/Desktop/Screenshot 2026-04-22 at 8.46.01 PM.png')

Then, I connected the codebase from my computer. For this, I used the databricks CLI,

https://docs.databricks.com/aws/en/dev-tools/cli/install

using the commands

``brew tap databricks/tap ``

``brew install databricks``

Then I ran these commands:

``databricks workspace export-dir /Workspace/Users/herst017@umn.edu/faers-dash .``

``databricks sync --watch . /Workspace/Users/herst017@umn.edu/faers-dash``

``databricks apps deploy faers-dash --source-code-path /Workspace/Users/herst017@umn.edu/faers-dash``

As long as you keep that running, any edits you make in your workspace will be synced. When you want to redeploy, just run the last command again.

I had Claude Code build me the app.yaml file, which just points databricks to the python file to run to start the dashboard.

**Data Loading**

To load the data, I uploaded it to a new volume, then I ran the bootstrap.ipynb script in my databricks workspace. This takes my parquet files that I uploaded and creates Delta tables for the app to use.
