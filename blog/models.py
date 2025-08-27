from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django_summernote.models import AbstractAttachment
from accounts.models import Organization


class BlogCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Blog Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class BlogPost(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name='posts')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='blog_posts')
    
    featured_image = models.ImageField(upload_to='blog/images/', blank=True, null=True)
    excerpt = models.TextField(max_length=500, help_text="Brief description of the post")
    content = models.TextField()
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    featured = models.BooleanField(default=False)
    
    tags = models.JSONField(default=list, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    views_count = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)
    
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'published_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Set published_at when status changes to PUBLISHED
        if self.status == 'PUBLISHED' and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title
    
    @property
    def is_published(self):
        return self.status == 'PUBLISHED'


class BlogComment(models.Model):
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_comments')
    content = models.TextField()
    
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"


class BlogPostAttachment(AbstractAttachment):
    """Attachment model for Summernote rich text editor"""
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    
    def __str__(self):
        return self.file.name if self.file else 'Attachment'