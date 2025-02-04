#!/bin/bash

unset KUBECONFIG

cd .. && docker build -f docker/Dockerfile.latest \
             -t dify-on-wechat2:$(date +%y%m%d) .
