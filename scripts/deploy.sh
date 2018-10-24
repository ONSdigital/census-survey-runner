#!/bin/bash

docker build -t onsdigital/census-survey-runner:${TRAVIS_COMMIT::8} -f Dockerfile .
docker build -t onsdigital/census-survey-runner-static:${TRAVIS_COMMIT::8} -f Dockerfile.static .
echo "Pushing with tag [${TRAVIS_COMMIT::8}]"
docker push onsdigital/census-survey-runner:${TRAVIS_COMMIT::8}
docker push onsdigital/census-survey-runner-static:${TRAVIS_COMMIT::8}

SPINNAKER_JSON="{\"artifacts\": [{\"type\": \"docker/image\", \"name\": \"onsdigital/census-survey-runner\", \"reference\": \"onsdigital/census-survey-runner:${TRAVIS_COMMIT::8}\"}]}"
echo "Pushing spinnaker webhook: $SPINNAKER_JSON"
curl -X POST -d "$SPINNAKER_JSON" -H "content-type: application/json" http://spinnaker-api.catd.onsdigital.uk/webhooks/webhook/survey-runner-travis
