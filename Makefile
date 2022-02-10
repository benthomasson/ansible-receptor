.PHONY: all build run shell push


all: build

build:
	ansible-builder build --tag quay.io/bthomass/receptor-local-demo --container-runtime podman

run:
	podman run -it --env-file env quay.io/bthomass/receptor-local-demo ftl-events rules.yml -i inventory.yml  --env-vars   webhook,connection_str,queue_name,token,management_url

shell:
	podman run -v /tmp/foo.sock:/tmp/foo.sock -it quay.io/bthomass/receptor-local-demo /bin/bash

push:
	podman push quay.io/bthomass/receptor-local-demo:latest
