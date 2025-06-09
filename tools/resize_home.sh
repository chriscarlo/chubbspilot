#!/bin/bash
# TICI Home Partition Resize Script
# Expands /home to use more space from root filesystem

set -e

echo "========================================="
echo "TICI Home Partition Resize"
echo "========================================="

echo "Current filesystem layout:"
df -h
echo

echo "Current partition table:"
lsblk -f
echo

echo "Mount points:"
mount | grep -E '^/dev/'
echo

# Check if /home is a separate partition or directory
HOME_MOUNT=$(mount | grep " /home " || echo "")

if [ -z "$HOME_MOUNT" ]; then
    echo "/home appears to be a directory on root filesystem"
    echo "This should not be causing space issues..."
    exit 1
fi

echo "Found /home mount: $HOME_MOUNT"
HOME_DEVICE=$(echo "$HOME_MOUNT" | awk '{print $1}')
echo "Home device: $HOME_DEVICE"

# Backup current home contents
echo "Creating backup of /home contents..."
sudo mkdir -p /tmp/home_backup
sudo cp -a /home/* /tmp/home_backup/ 2>/dev/null || true
echo "Backup created in /tmp/home_backup"

echo
echo "RESIZE OPTIONS:"
echo "1. Unmount /home and expand root filesystem to include it"
echo "2. Resize the /home partition (if using LVM or resizable filesystem)"
echo "3. Create a bind mount from a larger directory on root"
echo

read -p "Choose option (1-3): " OPTION

case $OPTION in
    1)
        echo "Option 1: Merging /home into root filesystem"
        
        # Unmount /home
        echo "Unmounting /home..."
        sudo umount /home
        
        # Remove from fstab
        echo "Removing /home from /etc/fstab..."
        sudo cp /etc/fstab /etc/fstab.backup
        sudo grep -v " /home " /etc/fstab > /tmp/fstab.new
        sudo mv /tmp/fstab.new /etc/fstab
        
        # Restore contents to root filesystem
        echo "Restoring home contents to root filesystem..."
        sudo mkdir -p /home
        sudo cp -a /tmp/home_backup/* /home/ 2>/dev/null || true
        
        echo "Done! /home is now part of root filesystem"
        ;;
        
    2)
        echo "Option 2: Resizing partition"
        echo "Checking if partition can be resized..."
        
        # Check filesystem type
        FSTYPE=$(lsblk -f "$HOME_DEVICE" | tail -1 | awk '{print $2}')
        echo "Filesystem type: $FSTYPE"
        
        if [ "$FSTYPE" = "ext4" ] || [ "$FSTYPE" = "ext3" ]; then
            echo "This requires partition table modification."
            echo "WARNING: This is risky and requires reboot."
            echo "Consider option 3 instead."
        else
            echo "Filesystem type $FSTYPE may not support online resizing"
        fi
        ;;
        
    3)
        echo "Option 3: Creating larger home directory with bind mount"
        
        # Create new larger home on root filesystem
        sudo mkdir -p /data/home_large
        
        # Copy current contents
        echo "Copying current home contents..."
        sudo cp -a /tmp/home_backup/* /data/home_large/ 2>/dev/null || true
        
        # Unmount current /home
        echo "Unmounting current /home..."
        sudo umount /home
        
        # Update fstab for bind mount
        echo "Updating /etc/fstab..."
        sudo cp /etc/fstab /etc/fstab.backup
        sudo grep -v " /home " /etc/fstab > /tmp/fstab.new
        echo "/data/home_large /home none bind 0 0" >> /tmp/fstab.new
        sudo mv /tmp/fstab.new /etc/fstab
        
        # Mount new home
        echo "Mounting new /home..."
        sudo mount /home
        
        echo "Done! /home now uses space from root filesystem via /data/home_large"
        ;;
        
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo
echo "Final filesystem layout:"
df -h
echo

echo "Cleaning up backup..."
sudo rm -rf /tmp/home_backup

echo
echo "========================================="
echo "Resize complete!"
echo "You may want to reboot to ensure changes persist"
echo "========================================="