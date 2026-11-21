#!/bin/bash

if sudo ufw status 2>/dev/null | grep -qi "Status: active"; then
    exit 0
else
    exit 1
fi
