from django.urls import path
from . import views

app_name = "cases"

urlpatterns = [
    # Case URLs
    path("", views.case_list, name="case_list"),
    path("case/<int:pk>/", views.case_detail, name="case_detail"),
    path("case/create/", views.case_create, name="case_create"),
    path("case/<int:pk>/edit/", views.case_update, name="case_update"),
    path("case/<int:pk>/publish/", views.case_publish, name="case_publish"),
    path("case/<int:pk>/to-draft/", views.case_to_draft, name="case_to_draft"),
    path("case/<int:pk>/delete/", views.case_delete, name="case_delete"),
    path("case/<int:pk>/share/", views.case_share, name="case_share"),
    # Patient URLs
    path("patients/", views.patient_list, name="patient_list"),
    path("patient/<int:pk>/", views.patient_detail, name="patient_detail"),
    path("patient/create/", views.patient_create, name="patient_create"),
    path("patient/<int:pk>/edit/", views.patient_update, name="patient_update"),
    path("patient/<int:pk>/delete/", views.patient_delete, name="patient_delete"),
    # Comment URLs
    path("case/<int:case_pk>/comment/", views.comment_add, name="comment_add"),
    path("comment/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
    # Opinion URLs
    path("case/<int:pk>/opinion/add/", views.add_opinion, name="add_opinion"),
    path("opinion/<int:pk>/update/", views.update_opinion, name="update_opinion"),
    path("opinion/<int:pk>/publish/", views.publish_opinion, name="publish_opinion"),
    path("opinion/<int:pk>/delete/", views.delete_opinion, name="delete_opinion"),
    # Image URLs
    path("case/<int:case_pk>/images/", views.image_list, name="image_list"),
    path("case/<int:case_pk>/image/upload/", views.image_upload, name="image_upload"),
    path("case/<int:case_pk>/image/upload-async/", views.image_upload_async, name="image_upload_async"),
    path("upload-progress/<str:task_id>/", views.image_upload_progress, name="image_upload_progress"),
    path("image/<int:pk>/", views.image_detail, name="image_detail"),
    path("image/<int:pk>/edit/", views.image_edit, name="image_edit"),
    path("image/<int:pk>/delete/", views.image_delete, name="image_delete"),
    path("image/<int:pk>/dicom/", views.dicom_viewer, name="dicom_viewer"),
    path("image/<int:pk>/dicom/preview/", views.dicom_to_jpg, name="dicom_preview"),
    path(
        "image-item/<int:pk>/dicom/thumbnail/",
        views.dicom_item_thumbnail,
        name="dicom_item_thumbnail",
    ),
    path(
        "image-item/<int:pk>/download/",
        views.download_image_item,
        name="download_image_item",
    ),
    path(
        "case/<int:pk>/dicom-series/",
        views.dicom_series_viewer,
        name="dicom_series_viewer",
    ),
    path(
        "case/<int:pk>/dicom-series/delete/",
        views.delete_dicom_series,
        name="delete_dicom_series",
    ),
    path(
        "case/<int:pk>/download-dicom/",
        views.download_dicom_series,
        name="download_dicom_series",
    ),
    path(
        "case/<int:pk>/download-images/",
        views.download_all_images,
        name="download_all_images",
    ),
    # Category URLs
    path("categories/", views.category_list, name="category_list"),
    path("category/create/", views.category_create, name="category_create"),
    # AJAX URLs
    path(
        "ajax/case/<int:pk>/status/",
        views.ajax_case_status_update,
        name="ajax_case_status_update",
    ),
    # API URLs
    path("api/check-draft/", views.check_draft_case, name="check_draft_case"),
    path(
        "delete-draft/",
        views.delete_all_activity_logs,
        name="delete_all_activity_logs",
    ),
]
