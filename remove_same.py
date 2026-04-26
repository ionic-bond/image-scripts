#!/usr/bin/python3

import os
import click

@click.group()
def cli():
    pass

def _is_image(filename):
    f = filename.lower()
    return f.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".svg"))

@cli.command()
@click.option('--base_dir', required=True, help="The base directory containing the original image files.")
@click.option('--scan_dir', required=True, help="The directory to scan for and remove duplicate image files.")
@click.option('--size_tolerance_percent', type=float, default=10.0,
              help="Maximum percentage difference in file size to consider files as duplicates. Default is 5.0.")
def run(base_dir, scan_dir, size_tolerance_percent):
    base_files_info = {}
    print(f"Scanning base directory: {base_dir}")
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if _is_image(file):
                path = os.path.normpath(os.path.join(root, file))
                try:
                    size = os.path.getsize(path)
                    if file not in base_files_info:
                        base_files_info[file] = {'path': path, 'size': size}
                except OSError as e:
                    print(f"Warning: Could not get size for {path}: {e}")

    print(f"Scanning directory for duplicates: {scan_dir}")
    for root, dirs, files in os.walk(scan_dir):
        for file in files:
            if _is_image(file):
                current_file_path = os.path.normpath(os.path.join(root, file))

                if file in base_files_info:
                    base_info = base_files_info[file]
                    base_file_path = base_info['path']
                    base_file_size = base_info['size']

                    if base_file_path != current_file_path:
                        filename_without_ext = os.path.splitext(file)[0]
                        
                        if len(filename_without_ext) > 6:
                            try:
                                current_file_size = os.path.getsize(current_file_path)
                                size_diff = abs(base_file_size - current_file_size)
                                max_allowed_diff = base_file_size * (size_tolerance_percent / 100.0)

                                if size_diff <= max_allowed_diff:
                                    os.remove(current_file_path)
                                    print(f'Removed duplicate: {current_file_path} (Base size: {base_file_size}, Duplicate size: {current_file_size})')
                                else:
                                    print(f"Skipped {current_file_path}: Size difference ({size_diff} bytes) is greater than allowed ({max_allowed_diff:.2f} bytes). Base size: {base_file_size}, Duplicate size: {current_file_size}.")
                            except OSError as e:
                                print(f"Warning: Could not get size or remove {current_file_path}: {e}")
                        else:
                            print(f"Skipped {current_file_path}: Filename without extension is not greater than 6 characters.")
    print("Scan complete.")

if __name__ == "__main__":
    cli()