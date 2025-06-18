#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path

try:
    from azure.storage.fileshare import ShareFileClient, ShareDirectoryClient
    from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
except ImportError:
    print("Error: Azure SDK not installed.", file=sys.stderr)
    print("Please install it: pip install azure-storage-file-share", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
# Assume script is run from the root of the openpilot repository
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_SOURCE_BASE_REL = "map_data_tiles_protobuf" # Relative to repo root
AZURE_SHARE_NAME = "mapdata"
AZURE_BASE_DIR = "protobuf_tiles" # Base directory within the share
CONN_STRING_PATH = "/persist/azure_conn_string"

def get_azure_connection_string(path: str) -> str | None:
    """Reads the Azure connection string from the specified file path."""
    try:
        with open(path, "r") as f:
            conn_str = f.read().strip()
        if not conn_str:
            print(f"Error: Connection string file '{path}' is empty.", file=sys.stderr)
            return None
        print(f"Successfully read connection string from {path}")
        return conn_str
    except FileNotFoundError:
        print(f"Error: Connection string file not found at '{path}'.", file=sys.stderr)
        print("Please ensure the file exists and contains your Azure Storage connection string.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error reading connection string from '{path}': {e}", file=sys.stderr)
        return None

def ensure_azure_directory_exists(conn_str: str, share_name: str, azure_dir_path: str):
    """Ensures a directory exists in Azure File Share, creating it if necessary."""
    if not azure_dir_path or azure_dir_path == '.':
        print(f"Skipping directory creation for root or empty path: '{azure_dir_path}'")
        return # No need to create the root

    print(f"Ensuring Azure directory exists: {share_name}/{azure_dir_path}")
    current_path = ""
    parts = Path(azure_dir_path).parts
    base_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, "") # Client for root

    for part in parts:
        if not part: continue
        # Ensure paths use forward slashes for Azure
        parent_path_for_client = current_path.replace(os.sep, '/')
        current_path = os.path.join(current_path, part)
        current_path_for_client = current_path.replace(os.sep, '/')

        try:
            dir_client = base_client.get_subdirectory_client(current_path_for_client)
            dir_client.create_directory()
            print(f"  Created Azure directory: {current_path_for_client}")
        except ResourceExistsError:
            # print(f"  Directory already exists: {current_path_for_client}") # Too verbose
            pass # Already exists, which is fine
        except Exception as e:
            print(f"  Error creating/checking directory {current_path_for_client}: {e}", file=sys.stderr)
            raise # Propagate error

def upload_tiles(conn_str: str, local_base_dir: Path, region: str):
    """Uploads tiles for a specific region to Azure."""
    local_region_dir = local_base_dir / region
    if not local_region_dir.is_dir():
        print(f"Error: Local region directory not found: {local_region_dir}", file=sys.stderr)
        return

    print(f"Starting upload for region '{region}' from '{local_region_dir}'...")
    print(f"Target Azure Share: '{AZURE_SHARE_NAME}'")
    print(f"Target Azure Base Directory: '{AZURE_BASE_DIR}'")

    upload_count = 0
    error_count = 0

    for root, dirs, files in os.walk(local_region_dir):
        root_path = Path(root)
        # Calculate relative path from the *base* source dir (e.g., "california/NorCal")
        relative_dir_path = root_path.relative_to(local_base_dir)
        azure_target_dir = Path(AZURE_BASE_DIR) / relative_dir_path
        azure_target_dir_str = str(azure_target_dir).replace(os.sep, '/') # Use forward slashes

        # Ensure the directory exists in Azure first
        try:
            ensure_azure_directory_exists(conn_str, AZURE_SHARE_NAME, azure_target_dir_str)
        except Exception as e:
            print(f"Critical Error: Failed to create Azure directory {azure_target_dir_str}. Skipping files within. Error: {e}", file=sys.stderr)
            error_count += len(files) # Count files in this dir as errors
            dirs[:] = [] # Don't recurse into subdirs if parent creation failed
            continue

        # Upload files in the current directory
        for filename in files:
            if not filename.endswith(".protobuf"):
                continue

            local_file_path = root_path / filename
            azure_filename = filename
            print(f"  Uploading {local_file_path} to {azure_target_dir_str}/{azure_filename}...")

            try:
                file_client = ShareFileClient.from_connection_string(
                    conn_str=conn_str,
                    share_name=AZURE_SHARE_NAME,
                    file_path=f"{azure_target_dir_str}/{azure_filename}" # Full path needed here
                )

                # Check if file exists and delete it first
                try:
                    file_client.get_file_properties() # Check existence
                    print(f"    File exists in Azure. Deleting before upload...")
                    file_client.delete_file()
                    print(f"    Deleted existing file.")
                except ResourceNotFoundError:
                    print(f"    File does not exist in Azure. Proceeding with upload.")
                    pass # File doesn't exist, no need to delete
                except Exception as del_e:
                    print(f"    Warning: Error checking/deleting existing file {azure_target_dir_str}/{azure_filename}: {del_e}", file=sys.stderr)
                    # Decide if we should continue or count as error? For now, try uploading anyway.

                # Upload the file (without overwrite argument)
                with open(local_file_path, "rb") as source_file:
                    file_client.upload_file(source_file) # Removed overwrite=True
                upload_count += 1
                print(f"    Successfully uploaded.")
            except FileNotFoundError:
                print(f"    Error: Local file not found during upload: {local_file_path}", file=sys.stderr)
                error_count += 1
            except Exception as e:
                print(f"    Error uploading {local_file_path}: {e}", file=sys.stderr)
                error_count += 1

    print("-" * 20)
    print(f"Upload complete for region '{region}'.")
    print(f"Successfully uploaded: {upload_count} files.")
    print(f"Errors encountered: {error_count} files.")
    print("-" * 20)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload map protobuf tiles to Azure File Share.")
    parser.add_argument("region", type=str, help="The region directory to upload (e.g., 'california').")
    parser.add_argument("--conn-string-file", type=str, default=CONN_STRING_PATH,
                        help=f"Path to the file containing the Azure connection string (default: {CONN_STRING_PATH}).")
    parser.add_argument("--local-base", type=str, default=LOCAL_SOURCE_BASE_REL,
                        help=f"Local base directory containing region subdirectories, relative to repo root (default: {LOCAL_SOURCE_BASE_REL}).")

    args = parser.parse_args()

    print("--- Azure Map Tile Uploader ---")

    connection_string = get_azure_connection_string(args.conn_string_file)
    if not connection_string:
        sys.exit(1)

    # Calculate absolute local path
    local_source_absolute = REPO_ROOT / args.local_base
    print(f"Using local source base directory: {local_source_absolute}")

    # Run the upload for the specified region
    upload_tiles(connection_string, local_source_absolute, args.region)

    print("--- Upload Script Finished ---")