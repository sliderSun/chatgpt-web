#!/bin/bash

read -p "Enter your desired username: " username
read -s -p "Enter your desired password: " password
htpasswd_file="./auth/.htpasswd"

if [ ! -f "$htpasswd_file" ]; then
    sudo touch "$htpasswd_file"
fi

sudo sh -c "echo -n '${username}:' >> $htpasswd_file"
sudo sh -c "openssl passwd -apr1 ${password} >> $htpasswd_file"

echo "Username: ${username}"
echo "Password: ${password}"
echo ".htpasswd file location: ${htpasswd_file}"
