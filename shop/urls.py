from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter

from . import views, api_views


# ═════════════════════════════════════════════════════════════
# REST API Router
# ═════════════════════════════════════════════════════════════

router = DefaultRouter()
router.register('categories', api_views.CategoryViewSet)
router.register('products',   api_views.ProductViewSet)
router.register('suppliers',  api_views.SupplierViewSet)
router.register('sales',      api_views.SaleViewSet)


urlpatterns = [
    # ── Dashboard ─────────────────────────────────────────────
    path('', views.dashboard, name='dashboard'),

    # ── Authentication ────────────────────────────────────────
    path('login/',  auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup,      name='signup'),

    # ── Password Reset ────────────────────────────────────────
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt',
             success_url='/password-reset/done/',
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/reset/done/',
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # ── Products ──────────────────────────────────────────────
    path('products/',                     views.product_list,   name='product_list'),
    path('products/add/',                 views.product_add,    name='product_add'),
    path('products/<int:pk>/edit/',       views.product_edit,   name='product_edit'),
    path('products/<int:pk>/delete/',     views.product_delete, name='product_delete'),

    # ── Categories ────────────────────────────────────────────
    path('categories/',                   views.category_list,   name='category_list'),
    path('categories/add/',               views.category_add,    name='category_add'),
    path('categories/<int:pk>/edit/',     views.category_edit,   name='category_edit'),
    path('categories/<int:pk>/delete/',   views.category_delete, name='category_delete'),

    # ── Sales ─────────────────────────────────────────────────
    path('sales/',                        views.sales_list,     name='sales_list'),
    path('sales/new/',                    views.sale_create,    name='sale_create'),
    path('sales/<int:pk>/',                views.sale_detail,   name='sale_detail'),

    # ── Suppliers ─────────────────────────────────────────────
    path('suppliers/',                    views.supplier_list,   name='supplier_list'),
    path('suppliers/add/',                views.supplier_add,    name='supplier_add'),
    path('suppliers/<int:pk>/delete/',    views.supplier_delete, name='supplier_delete'),

    # ── Reports ───────────────────────────────────────────────
    path('reports/',                      views.reports,         name='reports'),

    # ── Team Management (Multi-tenant) ────────────────────────
    path('team/',                         views.team_list,       name='team_list'),
    path('team/invite/',                  views.team_invite,     name='team_invite'),
    path('team/<int:pk>/remove/',         views.team_remove,     name='team_remove'),

    # ── Email Verification ───────────────────────────────────
    path('verify-email/<str:token>/', views.verify_email,        name='verify_email'),
    path('verify-otp/',                views.verify_otp,          name='verify_otp'),
    path('verification-sent/',         views.verification_sent,   name='verification_sent'),
    path('resend-verification/',       views.resend_verification, name='resend_verification'),
    # ── REST API ──────────────────────────────────────────────
    path('api/', include(router.urls)),
]