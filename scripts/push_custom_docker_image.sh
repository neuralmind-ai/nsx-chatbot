#!/bin/bash
set -ex

# Get the version number
BITBUCKET_BRANCH=$1

if echo $BITBUCKET_BRANCH | grep -o "SEARCHX-[0-9]*"; then
    VERSION=$(echo $BITBUCKET_BRANCH | grep -o "SEARCHX-[0-9]*")
elif echo $BITBUCKET_BRANCH | grep -o "release/*"; then
    VERSION="${BITBUCKET_BRANCH#release/}-dev"
else
    VERSION="dev-${BITBUCKET_COMMIT::8}"
fi

# Transform the version to lowercase
VERSION=${VERSION,,}
echo "The version is $VERSION"

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

# Tag and push the docker image
echo "Pushing docker image $IMAGE"
docker push $IMAGE:"${VERSION}"

echo "The docker image $IMAGE:$VERSION has been pushed to the Azure Container Registry"
echo "To pull the image from azure, run the following command:"
echo "docker pull $IMAGE:$VERSION"
