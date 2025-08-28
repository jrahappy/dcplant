from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, F, Count
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from cases.utils import ensure_user_profile
from .models import BlogPost, BlogCategory, BlogComment
from .forms import BlogPostForm, BlogCategoryForm, BlogCommentForm, BlogFilterForm


# Blog Post Views
@login_required
def post_list(request):
    """List all blog posts with filters"""
    profile = ensure_user_profile(request.user)
    
    # Get posts for user's organization
    posts = BlogPost.objects.filter(
        organization=profile.organization
    ).select_related('author', 'category')
    
    # Apply filters
    filter_form = BlogFilterForm(request.GET)
    
    if filter_form.is_valid():
        # Search filter
        search = filter_form.cleaned_data.get('search')
        if search:
            posts = posts.filter(
                Q(title__icontains=search) |
                Q(excerpt__icontains=search) |
                Q(content__icontains=search) |
                Q(tags__icontains=search)
            )
        
        # Category filter
        category = filter_form.cleaned_data.get('category')
        if category:
            posts = posts.filter(category=category)
        
        # Status filter
        status = filter_form.cleaned_data.get('status')
        if status:
            posts = posts.filter(status=status)
        
        # Featured filter
        featured = filter_form.cleaned_data.get('featured')
        if featured == 'true':
            posts = posts.filter(featured=True)
        elif featured == 'false':
            posts = posts.filter(featured=False)
    
    # Order by published date or created date
    posts = posts.order_by('-published_at', '-created_at')
    
    # Pagination
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_count': posts.count(),
    }
    return render(request, 'blog/post_list.html', context)


@login_required
def post_detail(request, slug):
    """Display a single blog post"""
    profile = ensure_user_profile(request.user)
    
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        organization=profile.organization
    )
    
    # Increment view count
    BlogPost.objects.filter(pk=post.pk).update(views_count=F('views_count') + 1)
    
    # Get comments
    comments = post.comments.filter(
        parent__isnull=True
    ).select_related('author').prefetch_related('replies')
    
    # Comment form
    comment_form = BlogCommentForm()
    
    # Related posts
    related_posts = BlogPost.objects.filter(
        organization=profile.organization,
        category=post.category,
        status='PUBLISHED'
    ).exclude(pk=post.pk)[:3]
    
    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'related_posts': related_posts,
    }
    return render(request, 'blog/post_detail.html', context)


@login_required
def post_create(request):
    """Create a new blog post"""
    profile = ensure_user_profile(request.user)
    
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.organization = profile.organization
            
            # Handle save_draft vs save_publish buttons
            if 'save_draft' in request.POST:
                post.status = 'DRAFT'
            elif 'save_publish' in request.POST:
                post.status = 'PUBLISHED'
                if not post.published_at:
                    post.published_at = timezone.now()
            
            post.save()
            
            messages.success(request, f'Blog post "{post.title}" created successfully!')
            
            if post.status == 'PUBLISHED':
                return redirect('blog:post_detail', slug=post.slug)
            else:
                return redirect('blog:post_edit', slug=post.slug)
    else:
        form = BlogPostForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create New Post',
    }
    return render(request, 'blog/post_form.html', context)


@login_required
def post_edit(request, slug):
    """Edit an existing blog post"""
    profile = ensure_user_profile(request.user)
    
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        organization=profile.organization
    )
    
    # Check permissions
    if not (request.user == post.author or profile.is_admin or request.user.is_staff):
        messages.error(request, 'You do not have permission to edit this post.')
        return redirect('blog:post_detail', slug=post.slug)
    
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            
            # Handle save_draft vs save_publish buttons
            if 'save_draft' in request.POST:
                post.status = 'DRAFT'
            elif 'save_publish' in request.POST:
                post.status = 'PUBLISHED'
                if not post.published_at:
                    post.published_at = timezone.now()
            
            post.save()
            messages.success(request, 'Blog post updated successfully!')
            return redirect('blog:post_detail', slug=post.slug)
    else:
        form = BlogPostForm(instance=post, user=request.user)
    
    context = {
        'form': form,
        'post': post,
        'title': f'Edit: {post.title}',
    }
    return render(request, 'blog/post_form.html', context)


@login_required
@require_http_methods(["POST"])
def post_delete(request, slug):
    """Delete a blog post"""
    profile = ensure_user_profile(request.user)
    
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        organization=profile.organization
    )
    
    # Check permissions
    if not (request.user == post.author or profile.is_admin or request.user.is_staff):
        return HttpResponseForbidden("You don't have permission to delete this post.")
    
    post_title = post.title
    post.delete()
    messages.success(request, f'Blog post "{post_title}" deleted successfully!')
    
    return redirect('blog:post_list')


# Blog Category Views
@login_required
def category_list(request):
    """List all blog categories"""
    categories = BlogCategory.objects.annotate(
        post_count=Count('posts')
    )
    
    context = {
        'categories': categories,
    }
    return render(request, 'blog/category_list.html', context)


@login_required
def category_create(request):
    """Create a new category"""
    profile = ensure_user_profile(request.user)
    
    # Check permissions
    if not (profile.is_admin or request.user.is_staff):
        messages.error(request, 'You do not have permission to create categories.')
        return redirect('blog:category_list')
    
    if request.method == 'POST':
        form = BlogCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect('blog:category_list')
    else:
        form = BlogCategoryForm()
    
    context = {
        'form': form,
        'title': 'Create New Category',
    }
    return render(request, 'blog/category_form.html', context)


@login_required
def category_edit(request, slug):
    """Edit a category"""
    profile = ensure_user_profile(request.user)
    
    # Check permissions
    if not (profile.is_admin or request.user.is_staff):
        messages.error(request, 'You do not have permission to edit categories.')
        return redirect('blog:category_list')
    
    category = get_object_or_404(BlogCategory, slug=slug)
    
    if request.method == 'POST':
        form = BlogCategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('blog:category_list')
    else:
        form = BlogCategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
        'title': f'Edit Category: {category.name}',
    }
    return render(request, 'blog/category_form.html', context)


@login_required
@require_http_methods(["POST"])
def category_delete(request, slug):
    """Delete a category"""
    profile = ensure_user_profile(request.user)
    
    # Check permissions
    if not (profile.is_admin or request.user.is_staff):
        return HttpResponseForbidden("You don't have permission to delete categories.")
    
    category = get_object_or_404(BlogCategory, slug=slug)
    
    # Check if category has posts
    if category.posts.exists():
        messages.error(request, 'Cannot delete category with existing posts.')
        return redirect('blog:category_list')
    
    category_name = category.name
    category.delete()
    messages.success(request, f'Category "{category_name}" deleted successfully!')
    
    return redirect('blog:category_list')


# Comment Views
@login_required
@require_http_methods(["POST"])
def comment_add(request, slug):
    """Add a comment to a blog post"""
    profile = ensure_user_profile(request.user)
    
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        organization=profile.organization
    )
    
    form = BlogCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        
        # Handle reply to comment
        parent_id = request.POST.get('parent_id')
        if parent_id:
            parent = get_object_or_404(BlogComment, pk=parent_id)
            comment.parent = parent
        
        comment.save()
        messages.success(request, 'Comment added successfully!')
    else:
        messages.error(request, 'Error adding comment.')
    
    return redirect('blog:post_detail', slug=post.slug)


@login_required
@require_http_methods(["POST"])
def comment_delete(request, pk):
    """Delete a comment"""
    profile = ensure_user_profile(request.user)
    
    comment = get_object_or_404(BlogComment, pk=pk)
    post = comment.post
    
    # Check permissions
    if not (request.user == comment.author or profile.is_admin or request.user.is_staff):
        return HttpResponseForbidden("You don't have permission to delete this comment.")
    
    comment.delete()
    messages.success(request, 'Comment deleted successfully!')
    
    return redirect('blog:post_detail', slug=post.slug)


# AJAX Views
@login_required
@require_http_methods(["POST"])
def ajax_like_post(request, slug):
    """AJAX endpoint to like/unlike a post"""
    profile = ensure_user_profile(request.user)
    
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        organization=profile.organization
    )
    
    # For simplicity, just toggle the like count
    # In a real app, you'd track which users liked which posts
    action = request.POST.get('action', 'like')
    
    if action == 'like':
        BlogPost.objects.filter(pk=post.pk).update(likes_count=F('likes_count') + 1)
        post.refresh_from_db()
        liked = True
    else:
        BlogPost.objects.filter(pk=post.pk).update(likes_count=F('likes_count') - 1)
        post.refresh_from_db()
        liked = False
    
    return JsonResponse({
        'success': True,
        'likes_count': post.likes_count,
        'liked': liked
    })


# Public Views (for published posts) - Keep the original public views
def blog_list(request):
    """List all published blog posts"""
    posts = BlogPost.objects.filter(status='PUBLISHED').select_related('author', 'category')
    
    # Category filter
    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(excerpt__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(posts, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for sidebar
    categories = BlogCategory.objects.all()
    
    # Get featured posts
    featured_posts = BlogPost.objects.filter(
        status='PUBLISHED',
        featured=True
    ).select_related('author')[:3]
    
    context = {
        'page_obj': page_obj,
        'posts': page_obj,
        'categories': categories,
        'featured_posts': featured_posts,
        'search_query': search_query,
        'current_category': category_slug,
    }
    return render(request, 'blog/list.html', context)


def blog_detail(request, slug):
    """Blog post detail view"""
    post = get_object_or_404(BlogPost, slug=slug, status='PUBLISHED')
    
    # Increment view count
    post.views_count += 1
    post.save(update_fields=['views_count'])
    
    # Get comments
    comments = post.comments.filter(is_approved=True, parent=None).select_related('author')
    
    # Get related posts
    related_posts = BlogPost.objects.filter(
        status='PUBLISHED',
        category=post.category
    ).exclude(id=post.id)[:3]
    
    context = {
        'post': post,
        'comments': comments,
        'related_posts': related_posts,
    }
    return render(request, 'blog/detail.html', context)