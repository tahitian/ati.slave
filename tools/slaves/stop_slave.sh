#!/bin/bash

slaves=(
)

for slave in ${slaves[@]}
do
    /var/www/ati/slave/tools/slaves/stop_slave.exp $slave
done
