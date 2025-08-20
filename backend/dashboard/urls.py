from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_home, name='home'),
    
    # Search
    path('search/', views.search, name='search'),
    
    # User
    path('profile/', views.profile, name='profile'),
    path('settings/', views.settings, name='settings'),
    path('switch-theme/', views.switch_theme, name='switch_theme'),
    
    # Admin
    path('reports/', views.reports, name='reports'),
    path('users/', views.users_list, name='users'),
    
    # Auth
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
]