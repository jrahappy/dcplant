from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Admin/Staff Blog Management URLs
    path('admin/', views.post_list, name='post_list'),
    path('admin/post/create/', views.post_create, name='post_create'),
    path('admin/post/<slug:slug>/', views.post_detail, name='post_detail'),
    path('admin/post/<slug:slug>/edit/', views.post_edit, name='post_edit'),
    path('admin/post/<slug:slug>/delete/', views.post_delete, name='post_delete'),
    
    # Category Management URLs
    path('admin/categories/', views.category_list, name='category_list'),
    path('admin/category/create/', views.category_create, name='category_create'),
    path('admin/category/<slug:slug>/edit/', views.category_edit, name='category_edit'),
    path('admin/category/<slug:slug>/delete/', views.category_delete, name='category_delete'),
    
    # Comment Management URLs
    path('admin/post/<slug:slug>/comment/', views.comment_add, name='comment_add'),
    path('admin/comment/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    
    # AJAX URLs
    path('admin/ajax/post/<slug:slug>/like/', views.ajax_like_post, name='ajax_like_post'),
    
    # Public Blog URLs (original)
    path('', views.blog_list, name='list'),
    path('<slug:slug>/', views.blog_detail, name='detail'),
]