from django.urls import path
from . import views

urlpatterns = [
    # Organization CRUD
    path('', views.organization_list_create, name='organization-list-create'),
    path('<slug:slug>/', views.organization_detail, name='organization-detail'),
    path('<slug:slug>/switch/', views.switch_organization, name='organization-switch'),

    # Members
    path('<slug:slug>/members/', views.organization_members, name='organization-members'),
    path('<slug:slug>/members/<int:user_id>/', views.organization_member_detail,
         name='organization-member-detail'),
    path('<slug:slug>/invite/', views.invite_member, name='organization-invite'),

    # Owner: delete
    path('<slug:slug>/delete/', views.delete_organization, name='organization-delete'),

    # Superadmin
    path('__superadmin/orgs/', views.superadmin_orgs, name='superadmin-orgs'),
    path('__superadmin/orgs/<slug:slug>/', views.superadmin_org_detail, name='superadmin-org-detail'),
    path('__superadmin/impersonate/<int:user_id>/', views.superadmin_impersonate,
         name='superadmin-impersonate'),
]
