#!/bin/bash

if dpkg-query -W -f='${Status}' ufw 2>/dev/null | grep -q "install ok installed"; then
    sudo ufw disable
fi
