#!/usr/bin/env python

"""
Thin wrapper around the "aws" command line interface (CLI) for use with LocalStack.

The "awslocal" CLI allows you to easily interact with your local services without
having to specify "--endpoint-url=http://..." for every single command.

Example:
Instead of the following command ...
aws --endpoint-url=https://localhost:4568 --no-verify-ssl kinesis list-streams
... you can simply use this:
awslocal kinesis list-streams

Options:
  Run "aws help" for more details on the aws CLI subcommands.
"""

import os
import sys
import subprocess
import six
from threading import Thread

PARENT_FOLDER = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.isdir(os.path.join(PARENT_FOLDER, ".venv")):
    sys.path.insert(0, PARENT_FOLDER)

from localstack_client import config


def get_service():
    for param in sys.argv[1:]:
        if not param.startswith("-"):
            return param


def get_service_endpoint(localstack_host=None):
    service = get_service()
    if service == "s3api":
        service = "s3"
    return config.get_service_endpoints(localstack_host=localstack_host).get(service)


def usage():
    print(__doc__.strip())


def to_str(s):
    if six.PY3 and not isinstance(s, six.string_types):
        s = s.decode("utf-8")
    return s


def run(cmd, env={}):
    def output_reader(pipe, out):
        with pipe:
            for line in iter(pipe.readline, b""):
                line = to_str(line)
                out.write(line)
                out.flush()

    process = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        env=env,
        shell=True,
    )

    Thread(target=output_reader, args=[process.stdout, sys.stdout]).start()
    Thread(target=output_reader, args=[process.stderr, sys.stderr]).start()

    process.wait()
    sys.exit(process.returncode)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        return usage()

    localstack_host = os.environ.get("LOCALSTACK_HOST")

    # get service and endpoint
    endpoint = get_service_endpoint(localstack_host=localstack_host)
    service = get_service()
    if not endpoint and service:
        print('ERROR: Unable to find LocalStack endpoint for service "%s"' % service)
        return sys.exit(1)

    # prepare cmd args
    cmd_args = list(sys.argv)
    cmd_args[0] = "aws"
    if endpoint:
        cmd_args.insert(1, "--endpoint-url=%s" % endpoint)
        if "https" in endpoint:
            cmd_args.insert(2, "--no-verify-ssl")

    # prepare env vars
    env_dict = os.environ.copy()
    env_dict["PYTHONWARNINGS"] = os.environ.get(
        "PYTHONWARNINGS", "ignore:Unverified HTTPS request"
    )
    env_dict["AWS_DEFAULT_REGION"] = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    env_dict["AWS_ACCESS_KEY_ID"] = os.environ.get(
        "AWS_ACCESS_KEY_ID", "_not_needed_locally_"
    )
    env_dict["AWS_SECRET_ACCESS_KEY"] = os.environ.get(
        "AWS_SECRET_ACCESS_KEY", "_not_needed_locally_"
    )

    # run the command
    run(cmd_args, env_dict)


if __name__ == "__main__":
    main()
