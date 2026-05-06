import json
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login as auth_login
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, F, ProtectedError
from django.utils import timezone

from .models import Product, Sale, Category, Supplier, SaleItem, Shop, UserProfile
from .forms import ProductForm, SignupForm
from .serializers import SaleCreateSerializer
from .utils import shop_required
from .email_utils import send_verification_email
from .utils import shop_required, role_required


# ═════════════════════════════════════════════════════════════
# AUTHENTICATION  +  EMAIL VERIFICATION
# ═════════════════════════════════════════════════════════════

# ── Update signup() — store email in session ──
def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                send_verification_email(request, user)
                request.session['pending_verification_email'] = user.email
                messages.success(
                    request,
                    f'Account created! Check {user.email} for your 6-digit verification code.'
                )
                return redirect('verification_sent')
            except Exception as e:
                # Email failed — show specific error, delete user so they can retry
                user.delete()
                messages.error(
                    request,
                    'Could not send verification email. '
                    'This usually means our email service is temporarily unavailable. '
                    'Please try again in a moment.'
                )
                return render(request, 'registration/signup.html', {'form': form})
    else:
        form = SignupForm()

    return render(request, 'registration/signup.html', {'form': form})

def verification_sent(request):
    """
    Shown after signup. Now displays a 6-digit OTP entry form.
    User can either enter the OTP here OR click the link in their email.
    """
    # Try to get email from session (set by signup view) or query string
    email = request.session.get('pending_verification_email', '')
    return render(request, 'registration/verification_sent.html', {
        'email': email,
    })

def verify_otp(request):
    """User entered the 6-digit OTP code. Verify and log them in."""
    if request.method != 'POST':
        return redirect('verification_sent')
 
    email = request.POST.get('email', '').strip()
    otp   = request.POST.get('otp', '').strip()
 
    if not email or not otp:
        messages.error(request, 'Please enter both email and verification code.')
        return redirect('verification_sent')
 
    # Find an UNVERIFIED user with this email
    try:
        user = User.objects.get(email__iexact=email, profile__email_verified=False)
    except User.DoesNotExist:
        messages.error(request, 'No unverified account found with that email.')
        return redirect('verification_sent')
 
    profile = user.profile
 
    # Check rate limit (max 5 attempts per OTP)
    if profile.otp_attempts >= 5:
        messages.error(
            request,
            'Too many incorrect attempts. Please request a new verification code.'
        )
        return redirect('verification_sent')
 
    # Check if OTP is still valid (15 min window)
    if not profile.is_otp_valid():
        messages.error(
            request,
            'This code has expired. Please request a new verification email.'
        )
        return redirect('verification_sent')
 
    # Check if OTP matches
    if profile.verification_otp != otp:
        profile.otp_attempts += 1
        profile.save()
        remaining = 5 - profile.otp_attempts
        messages.error(
            request,
            f'Incorrect code. {remaining} attempt{"s" if remaining != 1 else ""} remaining.'
        )
        return redirect('verification_sent')
        
    # ✅ All checks passed — activate the account
    profile.email_verified     = True
    profile.verification_token = ''
    profile.verification_otp   = ''
    profile.otp_attempts       = 0
    profile.save()
 
    # Clear pending email from session
    request.session.pop('pending_verification_email', None)
 
    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, f'Email verified! Welcome to {profile.shop.name}.')
    return redirect('dashboard')

def verify_email(request, token):
    """User clicked the link in their email."""
    profile = get_object_or_404(UserProfile, verification_token=token)

    if profile.email_verified:
        messages.info(request, 'Your email is already verified. Please sign in.')
        return redirect('login')

    if not profile.is_verification_token_valid():
        messages.error(
            request,
            'This verification link has expired. Please sign up again or contact support.'
        )
        return redirect('login')

    # Activate the account
    profile.email_verified     = True
    profile.verification_token = ''   # one-time use
    profile.save()

    # Auto-login after verification
    auth_login(request, profile.user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, f'Email verified! Welcome to {profile.shop.name}.')
    return redirect('dashboard')


def resend_verification(request):
    """Allow users to resend the verification email if it was lost."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email__iexact=email, profile__email_verified=False)
            send_verification_email(request, user)
        except User.DoesNotExist:
            pass  # silent — don't reveal whether email exists

        # Always show same message (security: prevents email enumeration)
        messages.success(
            request,
            f'If an unverified account exists for {email}, we sent a new verification link.'
        )
    return redirect('verification_sent')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


# ═════════════════════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════════════════════

@login_required
@shop_required

@login_required
@shop_required
def dashboard(request):
    today = timezone.now().date()
    shop  = request.shop
    role  = request.user.profile.role
    is_owner = role == 'owner'
    is_admin_or_owner = role in ('owner', 'admin')

    # ── Today's stats ──
    today_sales = Sale.objects.filter(shop=shop, created_at__date=today)
    today_total = today_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    today_count = today_sales.count()

    # ── Monthly stats ──
    monthly_sales = Sale.objects.filter(shop=shop, created_at__year=today.year, created_at__month=today.month)
    monthly_total = monthly_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    monthly_count = monthly_sales.count()

    all_products    = Product.objects.filter(shop=shop).select_related('category')
    low_stock_items = [p for p in all_products if p.is_low_stock]

    # ── Weekly chart data (last 7 days) ──
    week_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        total = Sale.objects.filter(
            shop=shop, created_at__date=day
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        week_data.append({'day': day.strftime('%a'), 'total': float(total)})

    # ── Top selling products this month ──
    top_products = SaleItem.objects.filter(
        sale__shop=shop,
        sale__created_at__year=today.year,
        sale__created_at__month=today.month
    ).values('product__name').annotate(
        total_qty=Sum('quantity'),
        total_rev=Sum(F('quantity') * F('unit_price'))
    ).order_by('-total_qty')[:5]

    # ══════════════════════════════════════════════════════════════
    # PROFIT CALCULATION  —  Owner only
    # ══════════════════════════════════════════════════════════════
    today_profit   = 0
    monthly_profit = 0
    total_profit   = 0
    total_revenue  = 0

    if is_owner:
        def calc_profit(items_qs):
            """Sum of (qty * unit_price) minus (qty * cost_price)."""
            revenue = items_qs.aggregate(
                total=Sum(F('quantity') * F('unit_price'))
            )['total'] or 0
            cost = items_qs.aggregate(
                total=Sum(F('quantity') * F('product__cost_price'))
            )['total'] or 0
            return revenue - cost

        # Today's profit
        today_items = SaleItem.objects.filter(
            sale__shop=shop, sale__created_at__date=today
        )
        today_profit = calc_profit(today_items)

        # This month's profit
        monthly_items = SaleItem.objects.filter(
            sale__shop=shop,
            sale__created_at__year=today.year,
            sale__created_at__month=today.month
        )
        monthly_profit = calc_profit(monthly_items)

        # All-time profit + revenue
        all_items = SaleItem.objects.filter(sale__shop=shop)
        total_profit = calc_profit(all_items)

        total_revenue = Sale.objects.filter(shop=shop).aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0

    return render(request, 'dashboard.html', {
        'today_total':      today_total,
        'today_count':      today_count,
        'monthly_total':    monthly_total,
        'monthly_count':    monthly_count,
        'total_products':   all_products.count(),
        'total_categories': Category.objects.filter(shop=shop).count(),
        'low_stock_items':  low_stock_items,
        'low_stock_count':  len(low_stock_items),
        'recent_sales':     Sale.objects.filter(shop=shop).order_by('-created_at')[:5],
        'top_products':     top_products,
        'week_data':        json.dumps(week_data),

        # ── Profit data (owner only) ──
        'show_profit':      is_owner,
        'today_profit':     today_profit,
        'monthly_profit':   monthly_profit,
        'total_profit':     total_profit,
        'total_revenue':    total_revenue,

        # ── Role flags ──
        'user_role':        role,
        'is_owner':         is_owner,
        'is_admin_or_owner': is_admin_or_owner,
    })
# ═════════════════════════════════════════════════════════════
# PRODUCTS
# ═════════════════════════════════════════════════════════════

@login_required
@shop_required
def product_list(request):
    products = Product.objects.filter(shop=request.shop).select_related('category', 'supplier')
    categories = Category.objects.filter(shop=request.shop)
    low_stock_count = sum(1 for p in products if p.is_low_stock)
    return render(request, 'products/list.html', {
        'products':        products,
        'categories':      categories,
        'low_stock_count': low_stock_count,
    })


@login_required
@shop_required
@role_required('owner', 'admin')
def product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, shop=request.shop)
        if form.is_valid():
            product = form.save(commit=False)
            product.shop = request.shop
            product.save()
            messages.success(request, 'Product added successfully!')
            return redirect('product_list')
    else:
        form = ProductForm(shop=request.shop)
    return render(request, 'products/form.html', {
        'form':    form,
        'title':   'Add Product',
        'product': None,
    })


@login_required
@shop_required
@role_required('owner', 'admin')
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, shop=request.shop)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product, shop=request.shop)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product, shop=request.shop)
    return render(request, 'products/form.html', {
        'form':    form,
        'title':   'Edit Product',
        'product': product,
    })


@login_required
@shop_required
@role_required('owner', 'admin')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, shop=request.shop)
    if request.method == 'POST':
        try:
            name = product.name
            product.delete()
            messages.success(request, f'"{name}" deleted successfully.')
        except ProtectedError:
            messages.error(
                request,
                f'Cannot delete "{product.name}" because it has sales history. '
                f'Instead, set its stock to 0 to stop selling it.'
            )
    return redirect('product_list')


# ═════════════════════════════════════════════════════════════
# CATEGORIES
# ═════════════════════════════════════════════════════════════

@login_required
@shop_required
def category_list(request):
    categories = Category.objects.filter(shop=request.shop).annotate(
        product_count=Count('products')
    ).order_by('name')
    return render(request, 'categories/list.html', {'categories': categories})


@login_required
@shop_required
@role_required('owner', 'admin')
def category_add(request):
    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
        elif Category.objects.filter(shop=request.shop, name__iexact=name).exists():
            messages.error(request, f'Category "{name}" already exists.')
        else:
            Category.objects.create(shop=request.shop, name=name, description=description)
            messages.success(request, f'Category "{name}" added successfully!')
    return redirect('category_list')


@login_required
@shop_required
@role_required('owner', 'admin')
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, shop=request.shop)
    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
        elif Category.objects.filter(shop=request.shop, name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, f'Category "{name}" already exists.')
        else:
            category.name        = name
            category.description = description
            category.save()
            messages.success(request, f'Category "{name}" updated!')
    return redirect('category_list')


@login_required
@shop_required
@role_required('owner', 'admin')
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, shop=request.shop)
    if request.method == 'POST':
        try:
            name = category.name
            category.delete()
            messages.success(request, f'Category "{name}" deleted.')
        except ProtectedError:
            messages.error(
                request,
                f'Cannot delete "{category.name}" — it has products assigned to it. '
                f'Reassign or delete those products first.'
            )
    return redirect('category_list')


# ═════════════════════════════════════════════════════════════
# SUPPLIERS
# ═════════════════════════════════════════════════════════════

@login_required
@shop_required
@role_required('owner', 'admin')
def supplier_list(request):
    suppliers = Supplier.objects.filter(shop=request.shop)
    return render(request, 'suppliers/list.html', {'suppliers': suppliers})


@login_required
@shop_required
@role_required('owner', 'admin')
def supplier_add(request):
    if request.method == 'POST':
        Supplier.objects.create(
            shop    = request.shop,
            name    = request.POST.get('name'),
            phone   = request.POST.get('phone', ''),
            email   = request.POST.get('email', ''),
            address = request.POST.get('address', ''),
        )
        messages.success(request, 'Supplier added!')
    return redirect('supplier_list')


@login_required
@shop_required
@role_required('owner', 'admin')
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk, shop=request.shop)
    if request.method == 'POST':
        supplier.delete()
        messages.success(request, 'Supplier deleted.')
    return redirect('supplier_list')


# ═════════════════════════════════════════════════════════════
# SALES (POS + History + Detail)
# ═════════════════════════════════════════════════════════════

@login_required
@shop_required
def sale_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'errors': {'detail': 'Invalid JSON'}},
                status=400
            )

        serializer = SaleCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            sale = serializer.save()
            return JsonResponse({
                'success':         True,
                'sale_number':     sale.sale_number,
                'total_amount':    float(sale.total_amount),
                'subtotal':        float(sale.subtotal),
                'discount_amount': float(sale.discount_amount),
            })
        return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)

    # GET — show POS page (only this shop's products)
    products = Product.objects.filter(
        shop=request.shop, stock_quantity__gte=0
    ).select_related('category')
    categories = Category.objects.filter(shop=request.shop)

    return render(request, 'sales/pos.html', {
        'products':   products,
        'categories': categories,
    })


@login_required
@shop_required
def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product__category'),
        pk=pk,
        shop=request.shop,
    )
    return render(request, 'sales/detail.html', {'sale': sale})


@login_required
@shop_required
def sales_list(request):
    sales = Sale.objects.filter(shop=request.shop).select_related('created_by').prefetch_related('items').order_by('-created_at')

    # Filters
    q         = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from')
    date_to   = request.GET.get('date_to')

    if q:
        sales = sales.filter(sale_number__icontains=q)
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)

    today       = timezone.now().date()
    today_sales = Sale.objects.filter(shop=request.shop, created_at__date=today)

    totals = Sale.objects.filter(shop=request.shop).aggregate(
        total_revenue = Sum('total_amount'),
        total_count   = Count('id'),
    )
    avg = (totals['total_revenue'] / totals['total_count']) if totals['total_count'] else 0

    return render(request, 'sales/list.html', {
        'sales':         sales,
        'total_count':   totals['total_count'] or 0,
        'total_revenue': totals['total_revenue'] or 0,
        'today_count':   today_sales.count(),
        'today_revenue': today_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        'avg_sale':      avg,
    })


# ═════════════════════════════════════════════════════════════
# REPORTS
# ═════════════════════════════════════════════════════════════

@login_required
@shop_required
@role_required('owner', 'admin')
def reports(request):
    today = timezone.now().date()
    year  = today.year
    month = today.month
    shop  = request.shop
    role  = request.user.profile.role
    is_owner = role == 'owner'

    monthly       = Sale.objects.filter(shop=shop, created_at__year=year, created_at__month=month)
    monthly_total = monthly.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    # Weekly breakdown
    weekly = []
    for week in range(1, 5):
        start = (week - 1) * 7 + 1
        end   = week * 7
        total = Sale.objects.filter(
            shop=shop,
            created_at__year=year,
            created_at__month=month,
            created_at__day__gte=start,
            created_at__day__lte=end,
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        weekly.append({'week': f'Week {week}', 'total': float(total)})

    # Top products this month
    top_products = SaleItem.objects.filter(
        sale__shop=shop,
        sale__created_at__year=year,
        sale__created_at__month=month
    ).values('product__name').annotate(
        total_qty=Sum('quantity'),
        total_rev=Sum(F('quantity') * F('unit_price'))
    ).order_by('-total_qty')[:10]

    low_stock_count = sum(
        1 for p in Product.objects.filter(shop=shop) if p.is_low_stock
    )

    # ══════════════════════════════════════════════════════════════
    # PROFIT — Owner only
    # ══════════════════════════════════════════════════════════════
    monthly_profit  = 0
    total_profit    = 0
    total_revenue   = 0
    weekly_profit   = []
    top_with_profit = []

    if is_owner:
        # Helper to compute profit for any SaleItem queryset
        def calc_profit(items_qs):
            revenue = items_qs.aggregate(
                total=Sum(F('quantity') * F('unit_price'))
            )['total'] or 0
            cost = items_qs.aggregate(
                total=Sum(F('quantity') * F('product__cost_price'))
            )['total'] or 0
            return float(revenue - cost)

        # ── Monthly profit ──
        monthly_items  = SaleItem.objects.filter(
            sale__shop=shop,
            sale__created_at__year=year,
            sale__created_at__month=month,
        )
        monthly_profit = calc_profit(monthly_items)

        # ── All-time profit ──
        all_items     = SaleItem.objects.filter(sale__shop=shop)
        total_profit  = calc_profit(all_items)
        total_revenue = float(
            Sale.objects.filter(shop=shop).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        )

        # ── Weekly profit (matches the weekly revenue chart) ──
        for week in range(1, 5):
            start = (week - 1) * 7 + 1
            end   = week * 7
            wk_items = SaleItem.objects.filter(
                sale__shop=shop,
                sale__created_at__year=year,
                sale__created_at__month=month,
                sale__created_at__day__gte=start,
                sale__created_at__day__lte=end,
            )
            weekly_profit.append({'week': f'Week {week}', 'profit': calc_profit(wk_items)})

        # ── Top products WITH profit per item ──
        # Re-query top products with cost info added
        top_with_profit = list(SaleItem.objects.filter(
            sale__shop=shop,
            sale__created_at__year=year,
            sale__created_at__month=month
        ).values('product__name').annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum(F('quantity') * F('unit_price')),
            total_cost=Sum(F('quantity') * F('product__cost_price')),
        ).order_by('-total_qty')[:10])

        # Add a profit field per row
        for item in top_with_profit:
            item['total_profit'] = (item['total_rev'] or 0) - (item['total_cost'] or 0)

    return render(request, 'reports/index.html', {
        'monthly_total':   monthly_total,
        'monthly_count':   monthly.count(),
        'monthly_sales':   monthly.order_by('-created_at'),
        'weekly_data':     json.dumps(weekly),
        'top_products':    top_products,
        'month_name':      today.strftime('%B %Y'),
        'low_stock_count': low_stock_count,

        # ── Profit context (owner only) ──
        'is_owner':        is_owner,
        'monthly_profit':  monthly_profit,
        'total_profit':    total_profit,
        'total_revenue':   total_revenue,
        'weekly_profit':   json.dumps(weekly_profit),
        'top_with_profit': top_with_profit,
    })


# ═════════════════════════════════════════════════════════════
# TEAM MANAGEMENT (Owner-only)
# ═════════════════════════════════════════════════════════════

@login_required
@shop_required
@role_required('owner', 'admin')
def team_list(request):
    """Show all users belonging to the current shop."""
    members = UserProfile.objects.filter(shop=request.shop).select_related('user').order_by('-role', 'user__username')
    return render(request, 'team/list.html', {
        'members':  members,
        'is_owner': request.user.profile.role == 'owner',
    })


@login_required
@shop_required
@role_required('owner', 'admin')
def team_invite(request):
    """Owner adds a new staff/admin to their shop. Auto-verifies their email."""
    if request.user.profile.role != 'owner':
        messages.error(request, 'Only the shop owner can add team members.')
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip()
        role     = request.POST.get('role', 'staff')
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, 'Username and password are required.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'That username is already taken.')
        else:
            user = User.objects.create_user(
                username=username, email=email, password=password
            )
            # Owner-invited members are auto-verified (no email step needed)
            UserProfile.objects.create(
                user=user,
                shop=request.shop,
                role=role,
                email_verified=True,
            )
            messages.success(
                request,
                f'Team member "{username}" added! Share these credentials with them.'
            )
            return redirect('team_list')

    return redirect('team_list')


@login_required
@shop_required
@role_required('owner')
def team_remove(request, pk):
    """Owner removes a team member from the shop."""
    if request.user.profile.role != 'owner':
        messages.error(request, 'Only the shop owner can remove team members.')
        return redirect('team_list')

    profile = get_object_or_404(UserProfile, pk=pk, shop=request.shop)
    if profile.user == request.user:
        messages.error(request, 'You cannot remove yourself.')
    elif request.method == 'POST':
        username = profile.user.username
        profile.user.delete()  # cascades to profile
        messages.success(request, f'"{username}" removed from team.')
    return redirect('team_list')