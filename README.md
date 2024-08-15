<!--- Badges start --->
<img src="https://img.shields.io/badge/repo%20status-in%20development%20(caution)-red" alt="Repository status is still in development (caution required)"/>

<!--- Badges end --->

<img src="https://github.com/datasciencecampus/awesome-campus/blob/master/ons_dsc_logo.png">

# ParliAI (Public edition)

# Introduction
## About
This is the open-source code repository for the internal ParliAI project, allowing other developers to replicate non-sensitive features of the project and to encourage future collaboration and development in this space. Please do contact us at [datasciencecampus@ons.gov.uk](datasciencecampus@ons.gov.uk) to discuss this or any of our other projects.

## Installation

You are strongly recommended to install resources into a virtual environment. Project setup can be achieved as follows:

``` bash
$ git clone https://github.com/datasciencecampus/parliai-public.git
$ cd parliai-public
$ python -m venv venv
$ source venv/bin/activate
$ python -m pip install --upgrade pip
$ python -m pip install .
```

> \[!NOTE\] If you intend on doing any development work, please install the package as editable (`-e`) and with the `dev` optional dependencies:
>
> ``` bash
> $ python -m pip install -e ".[dev]"
> ```
>
> Moreover, once you have installed the package, please install the pre-commit hooks. These hooks help us to ensure repository security and a consistent code style.

### Pre-commit actions
This repository contains a configuration of pre-commit hooks. These are language agnostic and focussed on repository security (such as detection of passwords and API keys). If approaching this project as a developer, you are encouraged to install and enable `pre-commits` by running the following in your shell:
   1. Install `pre-commit`:

      ```
      pip install pre-commit
      ```
   2. Enable `pre-commit`:

      ```
      pre-commit install
      ```
Once pre-commits are activated, whenever you commit to this repository a series of checks will be executed. The pre-commits include checking for security keys, large files and unresolved merge conflict headers. The use of active pre-commits are highly encouraged and the given hooks can be expanded with Python or R specific hooks that can automate the code style and linting. We are using `ruff` to ensure consistent Python code formatting.

**NOTE:** Pre-commit hooks execute Python, so it expects a working Python build.

## Usage
Details to follow...

### Workflow
Details to follow...


# Data Science Campus
At the [Data Science Campus](https://datasciencecampus.ons.gov.uk/about-us/) we apply data science, and build skills, for public good across the UK and internationally. Get in touch with the Campus at [datasciencecampus@ons.gov.uk](datasciencecampus@ons.gov.uk).

# License

<!-- Unless stated otherwise, the codebase is released under [the MIT Licence][mit]. -->

The code, unless otherwise stated, is released under [the MIT Licence][mit].

The documentation for this work is subject to [© Crown copyright][copyright] and is available under the terms of the [Open Government 3.0][ogl] licence.

[mit]: LICENCE
[copyright]: http://www.nationalarchives.gov.uk/information-management/re-using-public-sector-information/uk-government-licensing-framework/crown-copyright/
[ogl]: http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/
