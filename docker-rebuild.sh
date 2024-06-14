#!/bin/bash
imageName=xx:news-and-match-info
containerName=namc

docker build -t $imageName -f Dockerfile  .

echo Delete old container...
docker rm -f $containerName

echo Run new container...
docker run -d -p 9991:9991 --name $containerName $imageName
