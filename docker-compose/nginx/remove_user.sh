#!/bin/bash

htpasswd_file="./auth/.htpasswd"

if [ ! -f "$htpasswd_file" ]; then
    echo "No .htpasswd file found"
    exit 1
fi

read -p "Enter the username you want to remove: " username

# Check if the user already exists in the file
if ! grep -q "${username}:" "$htpasswd_file"; then
    echo "User not found in .htpasswd file"
    exit 1
fi

# Delete the user from the file
sudo sed -i "/${username}:/d" "$htpasswd_file"

echo "User ${username} has been removed from the .htpasswd file."
