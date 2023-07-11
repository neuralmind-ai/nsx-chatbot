#!/bin/bash
set -ex

# Get the current version number using poetry
VERSION=$(poetry version -s)

# Set the image name
IMAGE=${AZCR_USERNAME}.azurecr.io/${IMAGE_NAME}

# Login to docker
echo ${AZCR_PASSWORD} | docker login ${AZCR_USERNAME}.azurecr.io --username ${AZCR_USERNAME} --password-stdin

# Build the docker image
echo "Building docker image $IMAGE"
docker build --build-arg API_KEY=${API_KEY} \
             --build-arg AZURE_CHATBOT_ACCESS_KEY=${AZURE_CHATBOT_ACCESS_KEY} \
             --build-arg AZURE_CLIENT_ID=${AZURE_CLIENT_ID} \
             --build-arg AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET} \
             --build-arg AZURE_TENANT_ID=${AZURE_TENANT_ID} \
             --build-arg COSMOS_KEY=${COSMOS_KEY} \
             --build-arg ENVIRONMENT=${ENVIRONMENT} \
             --build-arg TOKEN=${TOKEN} \
             -t ${IMAGE}:"${VERSION}" .


if [ "$BITBUCKET_BRANCH" = "master" ]; then
    # Tag and push the docker image
    echo "Pushing docker image $IMAGE"
    docker push $IMAGE:"${VERSION}"
    # Tag and push the docker image as latest
    docker tag $IMAGE:"${VERSION}" $IMAGE:latest
    docker push $IMAGE:latest
    # Tag the release
    DATE=$(date +%Y-%m-%d)
    git tag -a "$VERSION" -m "NSX-Chatbot Release $VERSION at $DATE"
    # Push the tag
    git push origin --tags

elif [ "$BITBUCKET_BRANCH" = "staging" ]; then
    # Tag and push the develop image
    docker tag $IMAGE:"${VERSION}" $IMAGE:"${VERSION}dev"
    docker push $IMAGE:"${VERSION}dev"
fi
