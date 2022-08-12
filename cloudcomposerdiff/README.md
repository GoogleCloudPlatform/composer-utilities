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


## Running the application

### Prerequisites

 * Python version: application has been tested on python version 3.10
 * Composer version:  compatible with both Composer 1 and Composer 2
 * Composer version:  compatible with all Composer configurations
 * GCP IAM Permissions: executing user needs composer.environments.get [permission](https://cloud.google.com/composer/docs/how-to/access-control#permissions_for_api_methods)

### Clone repository

[Clone the code](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) from GitHub to your local machine

### Install locally with pip

navigate to the cloudcomposerdiff directory

from within the cloudcomposerdiff directory run the following command

```shell
pip install cloudcomposerdiff
```

### Authorizing the application using gcloud

Install [gcloud](https://cloud.google.com/sdk/gcloud)

Select a user which has access to both Cloud Composer environments to compare. This user
needs composer.environments.get [permission](https://cloud.google.com/composer/docs/how-to/access-control#permissions_for_api_methods)

With this user account, initialize gcloud:

```shell
gcloud init
```

Next, authorize the application to access Cloud Composer environments:

```shell
gcloud auth application-default login
```

### Use the appplication

cloudcomposerdiff is a command line tool. 

Details about expected inputs can be gathered by running the snippet below.

```shell
cloudcomposerdiff --help
```

To compare two environments the project ID, location & name of each composer environment
need to passed as input into the tool. 

```shell
cloudcomposerdiff \
--env1_project_id YOUR_PROJECT_ID \
--env1_location YOUR_ENV1_LOCATION \
--env1_name YOUR_ENV1_NAME \
--env2_project_id YOUR_PROJECT_ID \
--env2_location YOUR_ENV2_LOCATION \
--env2_name YOUR_ENV2_NAME
```

Upon executing the command, the tool will make APIs to Cloud Composer to fetch details
of the two specified environments. The details are then compared and the result diff
is sent back to the requesting user.