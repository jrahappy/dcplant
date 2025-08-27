from django.core.management.base import BaseCommand
from cases.models import Case, CaseImage


class Command(BaseCommand):
    help = 'Test DICOM file sorting for debugging'

    def add_arguments(self, parser):
        parser.add_argument(
            '--case-id',
            type=int,
            help='Case ID to test DICOM sorting'
        )

    def handle(self, *args, **options):
        case_id = options.get('case_id')
        
        if case_id:
            try:
                case = Case.objects.get(pk=case_id)
                self.stdout.write(f"\nTesting DICOM sorting for Case: {case.case_number}")
                self.stdout.write("=" * 60)
                
                # Get sorted DICOM images
                dicom_images = CaseImage.objects.get_dicom_series_sorted(case)
                
                if not dicom_images:
                    self.stdout.write(self.style.WARNING("No DICOM images found for this case"))
                    return
                
                self.stdout.write(f"\nFound {len(dicom_images)} DICOM images")
                self.stdout.write("\nSorted order (ascending by numeric value):")
                self.stdout.write("-" * 60)
                
                for idx, image in enumerate(dicom_images, 1):
                    self.stdout.write(
                        f"{idx:3d}. {image.filename} -> Order field: {image.order} | Numeric: {image.filename_numeric}"
                    )
                
                # Show the order field values for verification
                self.stdout.write("\nOrder field values:")
                self.stdout.write("-" * 60)
                orders = [img.order for img in dicom_images]
                self.stdout.write(f"Order values: {orders}")
                
                # Check if properly sorted by order field
                is_sorted = all(orders[i] <= orders[i+1] for i in range(len(orders)-1))
                if is_sorted:
                    self.stdout.write(self.style.SUCCESS("\n[OK] Files are properly sorted in ascending order"))
                else:
                    self.stdout.write(self.style.ERROR("\n[WARNING] Files may not be properly sorted"))
                    
            except Case.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Case with ID {case_id} not found"))
        else:
            # Show all cases with DICOM images
            cases_with_dicom = Case.objects.filter(images__is_dicom=True).distinct()
            
            if not cases_with_dicom:
                self.stdout.write(self.style.WARNING("No cases with DICOM images found"))
                return
                
            self.stdout.write("\nCases with DICOM images:")
            self.stdout.write("=" * 60)
            
            for case in cases_with_dicom:
                dicom_count = case.images.filter(is_dicom=True).count()
                self.stdout.write(
                    f"Case ID: {case.pk} | Number: {case.case_number} | "
                    f"Patient: {case.patient.full_name} | DICOM files: {dicom_count}"
                )
            
            self.stdout.write("\nRun with --case-id=<ID> to test sorting for a specific case")