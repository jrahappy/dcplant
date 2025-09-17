from celery import shared_task
from celery_progress.backend import ProgressRecorder
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from datetime import timedelta
import time
import logging
import os
import io
import base64
import pydicom

from .models import Case, CaseActivity, CaseImage, CaseImageItem
from accounts.models import User

logger = logging.getLogger(__name__)


def format_size(bytes_size):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


def process_file_in_chunks(file_content, chunk_size=1024 * 1024):  # 1MB chunks
    """Process file content in chunks for progress tracking"""
    chunks = []
    for i in range(0, len(file_content), chunk_size):
        chunks.append(file_content[i:i + chunk_size])
    return chunks


@shared_task(bind=True)
def process_image_upload(self, case_id, files_data, title_prefix, description, user_id, image_type='PHOTO'):
    """
    Process multiple image uploads in the background with progress tracking
    Handles both multiple small files and single large files with chunk processing
    """
    progress_recorder = ProgressRecorder(self)

    try:
        # Get case and user
        case = Case.objects.get(id=case_id)
        user = User.objects.get(id=user_id)

        total_files = len(files_data)
        uploaded_count = 0
        errors = []

        # Calculate total size for progress tracking
        total_size = sum(file_data.get('size', 0) for file_data in files_data)
        processed_size = 0

        # Determine if we're dealing with a single large file or multiple files
        is_single_large_file = total_files == 1 and total_size > 10 * 1024 * 1024  # > 10MB

        if is_single_large_file:
            progress_recorder.set_progress(0, 100, f'Uploading large file ({format_size(total_size)})...')

        # Generate a title for this upload batch
        from datetime import datetime
        if title_prefix:
            group_title = f"{title_prefix} - {datetime.now().strftime('%Y%m%d %H:%M')}"
        else:
            group_title = f"Upload - {datetime.now().strftime('%Y%m%d %H:%M')}"

        # Create CaseImage group for this upload
        with transaction.atomic():
            case_image = CaseImage.objects.create(
                case=case,
                title=group_title,
                description=description or f"Batch upload of {total_files} file(s)",
                uploaded_by=user,
            )

            # Process each file
            for index, file_data in enumerate(files_data):
                try:
                    file_name = file_data['name']
                    file_size = file_data.get('size', 0)

                    # Decode base64 file content
                    file_content_b64 = file_data['content']

                    # For large files, decode and process in chunks
                    if is_single_large_file or file_size > 5 * 1024 * 1024:  # > 5MB
                        # Decode in chunks to show progress
                        progress_recorder.set_progress(
                            10, 100,
                            f'Decoding {file_name} ({format_size(file_size)})...'
                        )

                        file_content = base64.b64decode(file_content_b64)

                        # Update progress for decoding complete
                        progress_recorder.set_progress(
                            30, 100,
                            f'Processing {file_name}...'
                        )
                    else:
                        # For smaller files, use the original progress tracking
                        progress_recorder.set_progress(
                            index,
                            total_files,
                            f'Processing file {index + 1} of {total_files}: {file_name}'
                        )
                        file_content = base64.b64decode(file_content_b64)

                    file_extension = os.path.splitext(file_name)[1].lower()

                    # Determine file type
                    is_dicom = file_extension in ['.dcm', '.dicom']
                    metadata = {}

                    if file_extension in ['.dcm', '.dicom']:
                        file_type = 'DICOM'
                    elif file_extension == '.pdf':
                        file_type = 'PDF'
                    elif file_extension == '.zip':
                        file_type = 'ZIP'
                    elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                        file_type = image_type
                    else:
                        file_type = 'OTHER'

                    # Extract DICOM metadata if applicable
                    if is_dicom:
                        try:
                            dicom_data = pydicom.dcmread(io.BytesIO(file_content))

                            # Extract metadata
                            if hasattr(dicom_data, 'PatientName'):
                                metadata['patient_name'] = str(dicom_data.PatientName)
                            if hasattr(dicom_data, 'StudyDate'):
                                metadata['study_date'] = str(dicom_data.StudyDate)
                            if hasattr(dicom_data, 'Modality'):
                                metadata['modality'] = str(dicom_data.Modality)
                            if hasattr(dicom_data, 'StudyDescription'):
                                metadata['study_description'] = str(dicom_data.StudyDescription)
                            if hasattr(dicom_data, 'InstanceNumber'):
                                metadata['instance_number'] = int(dicom_data.InstanceNumber)
                            if hasattr(dicom_data, 'SeriesInstanceUID'):
                                metadata['series_uid'] = str(dicom_data.SeriesInstanceUID)
                            if hasattr(dicom_data, 'StudyInstanceUID'):
                                metadata['study_uid'] = str(dicom_data.StudyInstanceUID)
                        except Exception as e:
                            logger.error(f"Error reading DICOM metadata: {e}")

                    # Update progress for saving
                    if is_single_large_file or file_size > 5 * 1024 * 1024:
                        progress_recorder.set_progress(
                            60, 100,
                            f'Saving {file_name} to database...'
                        )

                    # Create Django file
                    django_file = ContentFile(file_content, name=file_name)

                    # Create CaseImageItem
                    image_item = CaseImageItem.objects.create(
                        caseimage=case_image,
                        image=django_file,
                        image_type=file_type,
                        is_dicom=is_dicom,
                        is_primary=(
                            index == 0 and
                            not CaseImageItem.objects.filter(
                                caseimage__case=case,
                                is_primary=True
                            ).exists()
                        ),
                        metadata=metadata,
                        order=index,
                    )

                    uploaded_count += 1
                    logger.info(f"Successfully uploaded file {file_name} for case {case.case_number}")

                    # Update progress for large file completion
                    if is_single_large_file:
                        progress_recorder.set_progress(
                            90, 100,
                            f'Finalizing {file_name}...'
                        )

                    # Small delay to avoid overwhelming the system
                    time.sleep(0.1)

                    # Track processed size for overall progress
                    processed_size += file_size

                except Exception as e:
                    error_msg = f"{file_data['name']}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Error uploading file: {error_msg}")

            # Log activity
            if uploaded_count > 0:
                CaseActivity.objects.create(
                    case=case,
                    user=user,
                    activity_type='IMAGE_ADDED',
                    description=f'Added {uploaded_count} image(s) via background upload',
                    metadata={
                        'uploaded_count': uploaded_count,
                        'total_files': total_files,
                        'errors': errors
                    }
                )

        progress_recorder.set_progress(
            total_files,
            total_files,
            f'Upload complete! {uploaded_count} of {total_files} files uploaded successfully.'
        )

        return {
            'status': 'success',
            'uploaded_count': uploaded_count,
            'total_files': total_files,
            'errors': errors,
            'case_id': case_id
        }

    except Exception as e:
        logger.error(f"Error in image upload task: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(bind=True)
def process_case_images(self, case_id, image_ids):
    """
    Process multiple case images in the background
    This could include: resizing, generating thumbnails, extracting DICOM metadata, etc.
    """
    progress_recorder = ProgressRecorder(self)

    try:
        case = Case.objects.get(id=case_id)
        images = CaseImageItem.objects.filter(id__in=image_ids)
        total_images = images.count()

        for i, image in enumerate(images):
            # Update progress
            progress_recorder.set_progress(i, total_images, f'Processing image {i+1} of {total_images}')

            # Simulate processing (replace with actual image processing)
            time.sleep(1)

            # Example: Extract DICOM metadata if it's a DICOM file
            if image.is_dicom:
                # Add your DICOM processing logic here
                image.metadata['processed_at'] = timezone.now().isoformat()
                image.save()

            logger.info(f"Processed image {image.id} for case {case.case_number}")

        # Log activity
        CaseActivity.objects.create(
            case=case,
            activity_type='IMAGE_PROCESSED',
            description=f'Processed {total_images} images',
            metadata={'image_count': total_images}
        )

        return f'Successfully processed {total_images} images for case {case.case_number}'

    except Case.DoesNotExist:
        logger.error(f"Case {case_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error processing images: {str(e)}")
        raise


@shared_task(bind=True)
def generate_case_report(self, case_id, user_id, report_type='pdf'):
    """
    Generate a comprehensive case report in the background
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(0, 100, 'Starting report generation...')

        case = Case.objects.get(id=case_id)
        user = User.objects.get(id=user_id)

        progress_recorder.set_progress(20, 100, 'Gathering case data...')
        time.sleep(1)  # Simulate data gathering

        progress_recorder.set_progress(40, 100, 'Processing images...')
        time.sleep(1)  # Simulate image processing

        progress_recorder.set_progress(60, 100, 'Generating report...')
        time.sleep(1)  # Simulate report generation

        progress_recorder.set_progress(80, 100, 'Finalizing...')

        # Log activity
        CaseActivity.objects.create(
            case=case,
            user=user,
            activity_type='REPORT_GENERATED',
            description=f'Generated {report_type.upper()} report',
            metadata={'report_type': report_type}
        )

        progress_recorder.set_progress(100, 100, 'Report generated successfully!')

        return f'Report generated for case {case.case_number}'

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        raise


@shared_task
def send_case_notifications():
    """
    Send notifications for cases that need attention
    This task can be scheduled to run periodically
    """
    try:
        # Find cases that need review (example criteria)
        review_needed = Case.objects.filter(
            status='IN_REVIEW',
            updated_at__lte=timezone.now() - timedelta(days=3)
        )

        for case in review_needed:
            if case.assigned_to and case.assigned_to.email:
                send_mail(
                    subject=f'Case {case.case_number} needs review',
                    message=f'Case {case.case_number} has been in review for more than 3 days.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[case.assigned_to.email],
                    fail_silently=False,
                )

                logger.info(f"Sent notification for case {case.case_number}")

        return f'Sent notifications for {review_needed.count()} cases'

    except Exception as e:
        logger.error(f"Error sending notifications: {str(e)}")
        raise


@shared_task
def cleanup_old_activities():
    """
    Clean up old activity logs to maintain database performance
    This task can be scheduled to run weekly
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=90)

        # Delete activities older than 90 days
        deleted_count = CaseActivity.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]

        logger.info(f"Deleted {deleted_count} old activity records")
        return f'Cleaned up {deleted_count} old activity records'

    except Exception as e:
        logger.error(f"Error cleaning up activities: {str(e)}")
        raise


@shared_task(bind=True)
def bulk_update_cases(self, case_ids, updates):
    """
    Perform bulk updates on multiple cases
    """
    progress_recorder = ProgressRecorder(self)
    total_cases = len(case_ids)

    try:
        for i, case_id in enumerate(case_ids):
            progress_recorder.set_progress(i, total_cases, f'Updating case {i+1} of {total_cases}')

            with transaction.atomic():
                case = Case.objects.select_for_update().get(id=case_id)

                # Apply updates
                for field, value in updates.items():
                    if hasattr(case, field):
                        setattr(case, field, value)

                case.save()

                # Log activity
                CaseActivity.objects.create(
                    case=case,
                    activity_type='BULK_UPDATE',
                    description='Case updated via bulk operation',
                    metadata=updates
                )

            time.sleep(0.5)  # Small delay to prevent overwhelming the database

        return f'Successfully updated {total_cases} cases'

    except Exception as e:
        logger.error(f"Error in bulk update: {str(e)}")
        raise


@shared_task(bind=True)
def process_s3_images(self, case_id, s3_keys, title_prefix, description, user_id, image_type='PHOTO'):
    """
    Process images uploaded directly to S3
    """
    progress_recorder = ProgressRecorder(self)

    try:
        import boto3
        from django.conf import settings
        from botocore.exceptions import ClientError

        # Get case and user
        case = Case.objects.get(id=case_id)
        user = User.objects.get(id=user_id)

        total_files = len(s3_keys)
        processed_count = 0
        errors = []

        progress_recorder.set_progress(0, total_files, f'Processing {total_files} files from S3...')

        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        )

        # Generate a title for this upload batch
        from datetime import datetime
        if title_prefix:
            group_title = f"{title_prefix} - {datetime.now().strftime('%Y%m%d %H:%M')}"
        else:
            group_title = f"S3 Upload - {datetime.now().strftime('%Y%m%d %H:%M')}"

        # Create CaseImage group for this upload
        with transaction.atomic():
            case_image = CaseImage.objects.create(
                case=case,
                title=group_title,
                description=description or f"S3 upload of {total_files} file(s)",
                uploaded_by=user,
            )

            # Process each S3 file
            for index, s3_key in enumerate(s3_keys):
                try:
                    progress_recorder.set_progress(
                        index,
                        total_files,
                        f'Downloading file {index + 1} of {total_files} from S3'
                    )

                    # Get object metadata
                    response = s3_client.head_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        Key=s3_key
                    )

                    # Get original filename from metadata
                    original_filename = response['Metadata'].get('original-name', os.path.basename(s3_key))
                    file_extension = os.path.splitext(original_filename)[1].lower()

                    # Download file from S3
                    obj = s3_client.get_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        Key=s3_key
                    )
                    file_content = obj['Body'].read()

                    # Determine file type
                    if file_extension in ['.dcm', '.dicom']:
                        file_type = 'DICOM'
                        is_dicom = True
                    elif file_extension == '.pdf':
                        file_type = 'PDF'
                        is_dicom = False
                    elif file_extension == '.zip':
                        file_type = 'ZIP'
                        is_dicom = False
                    elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                        file_type = image_type
                        is_dicom = False
                    else:
                        file_type = 'OTHER'
                        is_dicom = False

                    # Extract DICOM metadata if applicable
                    metadata = {}
                    if is_dicom:
                        try:
                            dicom_data = pydicom.dcmread(io.BytesIO(file_content))

                            # Extract metadata
                            if hasattr(dicom_data, 'PatientName'):
                                metadata['patient_name'] = str(dicom_data.PatientName)
                            if hasattr(dicom_data, 'StudyDate'):
                                metadata['study_date'] = str(dicom_data.StudyDate)
                            if hasattr(dicom_data, 'Modality'):
                                metadata['modality'] = str(dicom_data.Modality)
                            if hasattr(dicom_data, 'StudyDescription'):
                                metadata['study_description'] = str(dicom_data.StudyDescription)
                        except Exception as e:
                            logger.error(f"Error reading DICOM metadata: {e}")

                    # Create Django file
                    django_file = ContentFile(file_content, name=original_filename)

                    # Create CaseImageItem
                    image_item = CaseImageItem.objects.create(
                        caseimage=case_image,
                        image=django_file,
                        image_type=file_type,
                        is_dicom=is_dicom,
                        is_primary=(
                            index == 0 and
                            not CaseImageItem.objects.filter(
                                caseimage__case=case,
                                is_primary=True
                            ).exists()
                        ),
                        metadata=metadata,
                        order=index,
                    )

                    # Delete the S3 file after successful processing (optional)
                    # s3_client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=s3_key)

                    processed_count += 1
                    logger.info(f"Successfully processed S3 file {original_filename} for case {case.case_number}")

                except ClientError as e:
                    error_msg = f"S3 error for {s3_key}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                except Exception as e:
                    error_msg = f"Error processing {s3_key}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # Log activity
            if processed_count > 0:
                CaseActivity.objects.create(
                    case=case,
                    user=user,
                    activity_type='IMAGE_ADDED',
                    description=f'Added {processed_count} image(s) via S3 upload',
                    metadata={
                        'processed_count': processed_count,
                        'total_files': total_files,
                        'errors': errors,
                        's3_upload': True
                    }
                )

        progress_recorder.set_progress(
            total_files,
            total_files,
            f'S3 processing complete! {processed_count} of {total_files} files processed successfully.'
        )

        return {
            'status': 'success',
            'processed_count': processed_count,
            'total_files': total_files,
            'errors': errors,
            'case_id': case_id
        }

    except Exception as e:
        logger.error(f"Error in S3 image processing task: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(bind=True)
def export_cases_to_csv(self, user_id, filters=None):
    """
    Export filtered cases to CSV format
    """
    progress_recorder = ProgressRecorder(self)

    try:
        import csv
        import io
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        user = User.objects.get(id=user_id)
        progress_recorder.set_progress(0, 100, 'Starting export...')

        # Apply filters to get cases
        cases = Case.objects.all()
        if filters:
            # Apply your filters here
            pass

        cases = cases.select_related('patient', 'assigned_to', 'organization')
        total_cases = cases.count()

        progress_recorder.set_progress(20, 100, f'Exporting {total_cases} cases...')

        # Create CSV file in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Case Number', 'Patient', 'Status', 'Priority',
            'Created Date', 'Assigned To', 'Organization'
        ])

        # Write data
        for i, case in enumerate(cases):
            if i % 10 == 0:
                progress = 20 + (60 * i / total_cases)
                progress_recorder.set_progress(progress, 100, f'Processing case {i+1} of {total_cases}')

            writer.writerow([
                case.case_number,
                case.patient.full_name,
                case.get_status_display(),
                case.get_priority_display(),
                case.created_at.strftime('%Y-%m-%d'),
                case.assigned_to.get_full_name() if case.assigned_to else '',
                case.organization.name
            ])

        progress_recorder.set_progress(80, 100, 'Saving file...')

        # Save file
        filename = f'cases_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        file_content = ContentFile(output.getvalue().encode('utf-8'))
        file_path = default_storage.save(f'exports/{filename}', file_content)

        progress_recorder.set_progress(100, 100, f'Export completed: {filename}')

        # Send email with download link if needed
        if user.email:
            # Add email sending logic here
            pass

        return f'Exported {total_cases} cases to {filename}'

    except Exception as e:
        logger.error(f"Error exporting cases: {str(e)}")
        raise