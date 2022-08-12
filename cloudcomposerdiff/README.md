# cloudcomposerdiff

Hey there ! If you need to diff two Cloud Composer environments, this tool is for you.

cloudcomposerdiff is a python command line tool to diff two Cloud Composer environments.

![gif showing environments with some matches & some differences](img/some_matches.gif)

As per the example above, this tool looks at various Cloud Composer environment
attributes and diffs them. It shows which attributes have different values across
environemnts, and what those values are. It also shows which attributes have a common
value across environments, and what this common value is.

When comparing two Cloud Composer environments that share no common attribute values
the "matching_value" column will be empty as per the example below:

![gif showing environments with zero matches](img/no_matches.gif)

When comparing two Cloud Composer environments that share common attributes values
the "matching_value" column will be populated and the "env_1_value" and "env_2_value"
columns will be empty. This is shown in the example below.

![gif showing environments with lots of matches](img/lots_of_matches.gif)


## Running this code

### Clone repository

[Clone the code](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) from GitHub to your local machine

### Install locally with pip

```shell
pip install cloudcomposerdiff
```

### Authorizing the application using gcloud

Install [gcloud](https://cloud.google.com/sdk/gcloud)

Select a user which has access to both composer environments to compare.

With this user account, initialize gcloud:

```shell
gcloud init
```

Next, authorize the application to access cloud composer environments:

```shell
gcloud auth application-default login
```

### Use the appplication

```shell
cloudcomposerdiff \
--env1_project_id YOUR_PROJECT_ID \
--env1_location YOUR_ENV1_LOCATION \
--env1_name YOUR_ENV1_NAME \
--env2_project_id YOUR_PROJECT_ID \
--env2_location YOUR_ENV2_LOCATION \
--env2_name YOUR_ENV2_NAME
```