from django.core.management.base import BaseCommand
from cases.models import CaseImage


class Command(BaseCommand):
    help = 'Update order field for existing DICOM images based on their filenames'

    def handle(self, *args, **options):
        # Get all DICOM images
        dicom_images = CaseImage.objects.filter(is_dicom=True)
        total = dicom_images.count()
        
        if not total:
            self.stdout.write(self.style.WARNING("No DICOM images found"))
            return
        
        self.stdout.write(f"Found {total} DICOM images to update")
        updated = 0
        
        for image in dicom_images:
            # Set order based on filename_numeric property
            new_order = image.filename_numeric
            if image.order != new_order:
                image.order = new_order
                image.save(update_fields=['order'])
                updated += 1
                self.stdout.write(f"Updated {image.filename}: order = {new_order}")
        
        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully updated {updated} DICOM images")
        )