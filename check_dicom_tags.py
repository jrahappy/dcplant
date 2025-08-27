"""
Script to check DICOM tags for ordering information
"""
import pydicom
import os
from pathlib import Path

# Path to a sample DICOM file
media_root = Path("D:/Dev/dcplant/media")
dicom_files = list(media_root.glob("**/*.dcm"))

if dicom_files:
    print(f"Found {len(dicom_files)} DICOM files")
    
    # Check the first few files
    for dcm_file in dicom_files[:5]:
        print(f"\n{'='*60}")
        print(f"File: {dcm_file.name}")
        print(f"{'='*60}")
        
        try:
            ds = pydicom.dcmread(str(dcm_file))
            
            # Common tags used for ordering DICOM series
            ordering_tags = {
                'Instance Number': (0x0020, 0x0013),
                'Slice Location': (0x0020, 0x1041),
                'Image Position Patient': (0x0020, 0x0032),
                'Temporal Position Identifier': (0x0020, 0x0100),
                'Stack Position Number': (0x0020, 0x9057),
                'In-Stack Position Number': (0x0020, 0x9057),
                'Frame Number': (0x0020, 0x9128),
                'Acquisition Number': (0x0020, 0x0012),
                'Acquisition Time': (0x0008, 0x0032),
            }
            
            for tag_name, tag_id in ordering_tags.items():
                if tag_id in ds:
                    value = ds[tag_id].value
                    print(f"{tag_name}: {value}")
                else:
                    print(f"{tag_name}: Not found")
                    
            # Also check Series and Study UIDs for grouping
            if (0x0020, 0x000E) in ds:
                print(f"Series Instance UID: {ds[0x0020, 0x000E].value}")
            if (0x0020, 0x000D) in ds:
                print(f"Study Instance UID: {ds[0x0020, 0x000D].value}")
                
        except Exception as e:
            print(f"Error reading DICOM file: {e}")
else:
    print("No DICOM files found in media directory")