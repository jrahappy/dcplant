"""
Management command to update DICOM images with Instance Number from metadata
"""
from django.core.management.base import BaseCommand
from cases.models import CaseImage
import pydicom
import os


class Command(BaseCommand):
    help = 'Update DICOM images to extract and set Instance Number for proper ordering'

    def handle(self, *args, **options):
        # Get all DICOM images
        dicom_images = CaseImage.objects.filter(is_dicom=True)
        total = dicom_images.count()
        
        self.stdout.write(f"Found {total} DICOM images to process")
        
        updated = 0
        errors = 0
        
        for image in dicom_images:
            try:
                # Check if file exists
                if not os.path.exists(image.image.path):
                    self.stdout.write(self.style.WARNING(f"File not found: {image.image.path}"))
                    errors += 1
                    continue
                
                # Read DICOM file
                ds = pydicom.dcmread(image.image.path)
                
                # Extract Instance Number and other metadata
                metadata = image.metadata or {}
                
                # Update Instance Number
                if hasattr(ds, 'InstanceNumber'):
                    instance_number = int(ds.InstanceNumber)
                    metadata['instance_number'] = instance_number
                    image.order = instance_number
                    
                    # Also extract other useful metadata if not present
                    if hasattr(ds, 'SeriesInstanceUID') and 'series_uid' not in metadata:
                        metadata['series_uid'] = str(ds.SeriesInstanceUID)
                    if hasattr(ds, 'StudyInstanceUID') and 'study_uid' not in metadata:
                        metadata['study_uid'] = str(ds.StudyInstanceUID)
                    if hasattr(ds, 'SliceLocation'):
                        metadata['slice_location'] = float(ds.SliceLocation)
                    
                    image.metadata = metadata
                    image.save()
                    updated += 1
                    
                    self.stdout.write(f"Updated {image.filename}: Instance Number = {instance_number}")
                else:
                    self.stdout.write(self.style.WARNING(f"No Instance Number in {image.filename}"))
                    # Fall back to filename-based ordering
                    image.order = image.filename_numeric
                    image.save()
                    updated += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing {image.id}: {e}"))
                errors += 1
        
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} DICOM images"))
        if errors:
            self.stdout.write(self.style.WARNING(f"Encountered {errors} errors"))