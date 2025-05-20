#!/bin/bash

modprobe -D facetimehd &&
	{
		echo "facetimehd driver already installed"
		exit 0
	}
[[ ! -d "facetimehd" ]] &&
	git clone https://github.com/patjak/facetimehd.git
[[ ! -d "facetimehd-firmware" ]] &&
	git clone https://github.com/patjak/facetimehd-firmware.git
# install dependencies
sudo apt install curl linux-headers-generic cpio
# Compile driver
cd facetimehd-firmware
make
sudo make install
# Install driver
cd ../facetimehd
# Create signing_key.pem, required by driver installation
# https://superuser.com/a/1322832
certs_directory=$(find /usr/src/*-generic/certs | head -n 1)
[[ -z "certs_directory" ]] && {
	echo "Certs directory not found"
	exit 1
}
if [[ ! -f "$certs_directory/signing_key.pem" ]]; then
	tee signing_key.config <<EOF
[ req ]
default_bits = 4096
distinguished_name = req_distinguished_name
prompt = no
string_mask = utf8only
x509_extensions = myexts

[ req_distinguished_name ]
CN = Modules

[ myexts ]
basicConstraints=critical,CA:FALSE
keyUsage=digitalSignature
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
EOF
	openssl req -new -nodes -utf8 -sha512 -days 36500 -batch -x509 -config signing_key.config -outform DER -out signing_key.x509 -keyout signing_key.pem
	sudo mv signing_key.pem signing_key.x509 $certs_directory
fi
# Install driver
make
sudo make install
sudo depmod
sudo modprobe facetimehd
rg -q facetimehd /etc/modules ||
	echo facetimehd | sudo tee -a /etc/modules
# Clean up
cd ..
rm -rf facetimehd facetimehd-firmware
