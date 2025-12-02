FROM alpine:3.20

RUN apk add --no-cache \
  curl \
  bash \
  jq \
  unzip \
  bash \
  python3 \
  py3-pip \
  aws-cli

RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

ENTRYPOINT ["/bin/bash"]
