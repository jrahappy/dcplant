from django import forms
from django_summernote.widgets import SummernoteWidget, SummernoteInplaceWidget
from .models import BlogPost, BlogCategory, BlogComment


class BlogCategoryForm(forms.ModelForm):
    """Form for creating and updating blog categories"""
    class Meta:
        model = BlogCategory
        fields = ['name', 'slug', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].help_text = 'Leave blank to auto-generate from name'


class BlogPostForm(forms.ModelForm):
    """Form for creating and updating blog posts with Summernote editor"""
    class Meta:
        model = BlogPost
        fields = [
            'title', 'slug', 'category', 'featured_image',
            'excerpt', 'content', 'status', 'featured',
            'tags', 'meta_description'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'featured_image': forms.FileInput(attrs={'class': 'form-control'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'content': SummernoteWidget(),  # Rich text editor
            'status': forms.Select(attrs={'class': 'form-select'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter tags separated by commas'
            }),
            'meta_description': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': 160,
                'placeholder': 'SEO meta description (max 160 characters)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make slug optional (auto-generate from title)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Leave blank to auto-generate from title'
        
        # Filter categories by active ones
        self.fields['category'].queryset = BlogCategory.objects.all()
        
        # Convert tags from list to comma-separated string for display
        if self.instance and self.instance.pk:
            if isinstance(self.instance.tags, list):
                self.initial['tags'] = ', '.join(self.instance.tags)
    
    def clean_tags(self):
        """Convert comma-separated tags to list"""
        tags = self.cleaned_data.get('tags', '')
        if tags:
            # Split by comma, strip whitespace, remove empty strings
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            return tag_list
        return []
    
    def clean_slug(self):
        """Auto-generate slug if not provided"""
        slug = self.cleaned_data.get('slug')
        if not slug and self.cleaned_data.get('title'):
            from django.utils.text import slugify
            slug = slugify(self.cleaned_data['title'])
        return slug


class BlogCommentForm(forms.ModelForm):
    """Form for adding comments to blog posts"""
    class Meta:
        model = BlogComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Write your comment here...'
            })
        }


class BlogFilterForm(forms.Form):
    """Form for filtering blog posts"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search posts...'
        })
    )
    category = forms.ModelChoiceField(
        required=False,
        queryset=BlogCategory.objects.all(),
        empty_label='All Categories',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status')] + BlogPost.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    featured = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('true', 'Featured Only'), ('false', 'Non-Featured')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )