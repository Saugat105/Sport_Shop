from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import Shop, UserProfile, Category, Supplier, Product, Sale, SaleItem


# ═════════════════════════════════════════════════════════════
# INLINES — show related data inside the Shop detail page
# ═════════════════════════════════════════════════════════════

class UserProfileInline(admin.TabularInline):
    """Show all team members of a shop on its detail page."""
    model = UserProfile
    extra = 0
    autocomplete_fields = ['user']
    fields = ['user', 'role', 'email_verified']
    verbose_name        = 'Team Member'
    verbose_name_plural = '👥 Team Members'


class CategoryInline(admin.TabularInline):
    model = Category
    extra = 0
    fields = ['name', 'description']
    verbose_name        = 'Category'
    verbose_name_plural = '🏷️ Categories'
    show_change_link = True


class SupplierInline(admin.TabularInline):
    model = Supplier
    extra = 0
    fields = ['name', 'phone', 'email']
    verbose_name        = 'Supplier'
    verbose_name_plural = '🚚 Suppliers'
    show_change_link = True


# ═════════════════════════════════════════════════════════════
# SHOP — central view; click a shop to see EVERYTHING
# ═════════════════════════════════════════════════════════════

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display    = [
        'name', 'owner_name', 'phone', 'email', 'is_active',
        'team_count', 'product_count', 'sales_count', 'created_at'
    ]
    list_filter     = ['is_active', 'created_at']
    search_fields   = ['name', 'owner_name', 'email', 'phone']
    readonly_fields = ['created_at', 'view_products_link', 'view_sales_link']
    date_hierarchy  = 'created_at'

    fieldsets = (
        ('Shop Info', {
            'fields': ('name', 'owner_name', 'address', 'phone', 'email', 'is_active'),
        }),
        ('Quick Links', {
            'fields': ('view_products_link', 'view_sales_link'),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    inlines = [UserProfileInline, CategoryInline, SupplierInline]

    @admin.display(description='Team', ordering='users__count')
    def team_count(self, obj):
        return obj.users.count()

    @admin.display(description='Products')
    def product_count(self, obj):
        return obj.products.count()

    @admin.display(description='Sales')
    def sales_count(self, obj):
        return obj.sales.count()

    @admin.display(description='View all products')
    def view_products_link(self, obj):
        if not obj.pk:
            return '—'
        url = reverse('admin:shop_product_changelist') + f'?shop__id__exact={obj.pk}'
        return format_html('<a class="button" href="{}">📦 See all {} products</a>',
                           url, obj.products.count())

    @admin.display(description='View all sales')
    def view_sales_link(self, obj):
        if not obj.pk:
            return '—'
        url = reverse('admin:shop_sale_changelist') + f'?shop__id__exact={obj.pk}'
        return format_html('<a class="button" href="{}">🧾 See all {} sales</a>',
                           url, obj.sales.count())


# ═════════════════════════════════════════════════════════════
# USER PROFILE
# ═════════════════════════════════════════════════════════════

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display    = ['user', 'shop', 'role', 'email_verified']
    list_filter     = ['shop', 'role', 'email_verified']    # shop filter FIRST
    search_fields   = ['user__username', 'user__email', 'shop__name']
    autocomplete_fields = ['user', 'shop']
    list_select_related = ['user', 'shop']


# ═════════════════════════════════════════════════════════════
# CATEGORY
# ═════════════════════════════════════════════════════════════

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display    = ['name', 'shop', 'product_count', 'created_at']
    list_filter     = ['shop', 'created_at']
    search_fields   = ['name', 'shop__name']
    autocomplete_fields = ['shop']
    list_select_related = ['shop']

    @admin.display(description='Products')
    def product_count(self, obj):
        return obj.products.count()


# ═════════════════════════════════════════════════════════════
# SUPPLIER
# ═════════════════════════════════════════════════════════════

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display    = ['name', 'shop', 'phone', 'email', 'product_count', 'created_at']
    list_filter     = ['shop', 'created_at']
    search_fields   = ['name', 'phone', 'email', 'shop__name']
    autocomplete_fields = ['shop']
    list_select_related = ['shop']

    @admin.display(description='Products')
    def product_count(self, obj):
        return obj.products.count()


# ═════════════════════════════════════════════════════════════
# PRODUCT
# ═════════════════════════════════════════════════════════════

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display    = ['name', 'shop', 'category', 'supplier',
                       'price', 'cost_price', 'stock_quantity', 'stock_status']
    list_filter     = ['shop', 'category', 'supplier', 'created_at']
    search_fields   = ['name', 'description', 'shop__name', 'category__name']
    autocomplete_fields = ['shop', 'category', 'supplier']
    list_select_related = ['shop', 'category', 'supplier']
    list_editable   = ['stock_quantity']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('shop', 'name', 'category', 'supplier', 'description'),
        }),
        ('Pricing', {
            'fields': ('price', 'cost_price'),
        }),
        ('Stock', {
            'fields': ('stock_quantity', 'low_stock_threshold'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Status')
    def stock_status(self, obj):
        if obj.stock_quantity == 0:
            return '🔴 Out'
        if obj.is_low_stock:
            return '🟡 Low'
        return '🟢 OK'


# ═════════════════════════════════════════════════════════════
# SALE  (with inline items)
# ═════════════════════════════════════════════════════════════

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    autocomplete_fields = ['product']
    readonly_fields = ['unit_price']
    fields = ['product', 'quantity', 'unit_price']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display    = ['sale_number', 'shop', 'created_by', 'created_at',
                       'items_count', 'subtotal', 'discount_amount', 'total_amount']
    list_filter     = ['shop', 'discount_type', 'created_at', 'created_by']
    search_fields   = ['sale_number', 'shop__name', 'created_by__username', 'notes']
    list_select_related = ['shop', 'created_by']
    autocomplete_fields = ['shop', 'created_by']
    date_hierarchy  = 'created_at'
    readonly_fields = ['created_at', 'subtotal', 'discount_amount', 'total_amount']
    inlines = [SaleItemInline]

    fieldsets = (
        ('Sale Info', {
            'fields': ('shop', 'sale_number', 'created_by', 'created_at', 'notes'),
        }),
        ('Discount', {
            'fields': ('discount_type', 'discount_value', 'discount_amount'),
        }),
        ('Totals', {
            'fields': ('subtotal', 'total_amount'),
        }),
    )

    @admin.display(description='Items')
    def items_count(self, obj):
        return obj.items.count()


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display    = ['sale', 'product', 'quantity', 'unit_price', 'line_subtotal']
    list_filter     = ['sale__shop']
    search_fields   = ['sale__sale_number', 'product__name']
    autocomplete_fields = ['sale', 'product']
    list_select_related = ['sale', 'product']

    @admin.display(description='Subtotal')
    def line_subtotal(self, obj):
        return f'Rs. {obj.subtotal}'


# ═════════════════════════════════════════════════════════════
# Site branding
# ═════════════════════════════════════════════════════════════

admin.site.site_header  = 'Sport Shop Nepal — Admin'
admin.site.site_title   = 'Sport Shop Admin'
admin.site.index_title  = 'Multi-Shop Database Management'