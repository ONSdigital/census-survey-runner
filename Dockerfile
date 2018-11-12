FROM golang:alpine as builder

RUN apk update && apk add git && apk add ca-certificates

RUN go get cloud.google.com/go/storage
RUN go get github.com/satori/go.uuid

COPY . $GOPATH/src/onsdigital/surveyrunner
WORKDIR $GOPATH/src/onsdigital/surveyrunner

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /go/bin/main

FROM scratch

COPY --from=builder /go/bin/main /go/bin/main
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

COPY flat_templates /flat_templates
COPY static /static

EXPOSE 5000

ENTRYPOINT ["/go/bin/main"]
