from django.urls import path

from . import views

app_name = 'tournaments'

urlpatterns = [
    path('', views.tournament_list, name='list'),
    path('join/', views.join_tournament, name='join'),
    path('admin/', views.staff_tournament_admin, name='staff_admin'),
    path('admin/update-fixture/', views.staff_update_fixture, name='staff_update_fixture'),
    path('admin/sync-results/', views.staff_sync_results, name='staff_sync_results'),
    path('admin/<slug:slug>/toggle-active/', views.staff_toggle_tournament_active, name='staff_toggle_active'),
    path('<slug:slug>/', views.tournament_detail, name='detail'),
    path('<slug:slug>/fixture/', views.fixture, name='fixture'),
    path('<slug:slug>/leaderboard/', views.leaderboard, name='leaderboard'),
    path('<slug:slug>/predictions/', views.my_predictions, name='predictions'),
    path('<slug:slug>/members/', views.members, name='members'),
    path('<slug:slug>/members/<int:user_id>/predictions/', views.member_predictions, name='member_predictions'),
    path('<slug:slug>/matches/<int:match_id>/', views.match_detail, name='match_detail'),
]
