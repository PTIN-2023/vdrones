#!/bin/bash

containers=$(docker ps -a | grep virtual-dron | tail -n +2 | awk '{print $1}')

for container in $containers
do 
    echo "stopping container $container ..."
    docker stop $container 2> /dev/null
    
    echo "deleting container $container ..."
    docker rm $container 2> /dev/null  
done

images=$(docker images | grep virtual-dron | tail -n +2 | awk '{print $1}')

for image in $images
do
    echo "deleting docker image $image ..."
    docker rmi $image 2> /dev/null
done

echo "building virtual-dron docker image"
docker build -t virtual-dron . 2> /dev/null

for dron_number in {1..10}
do
    echo "creating virtual-dron containter for dron number $dron_number"
    docker run -d --name virtual-dron-$dron_number virtual-dron --id $dron_number 2> /dev/null
done