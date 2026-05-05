from django.db import models
from django.contrib.auth.models import User


# ═════════════════════════════════════════════════════════════
# TENANCY MODELS
# ═════════════════════════════════════════════════════════════

class Shop(models.Model):
    """Each shop is one tenant of the system."""
    name       = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=100)
    address    = models.TextField(blank=True)
    phone      = models.CharField(max_length=20, blank=True)
    email      = models.EmailField(blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Links each user to their shop and stores their role + email verification."""
    ROLES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=10, choices=ROLES, default='staff')

    # ── Email verification (link OR OTP) ──
    email_verified         = models.BooleanField(default=False)
    verification_token     = models.CharField(max_length=64, blank=True)   # for link
    verification_otp       = models.CharField(max_length=6,  blank=True)   # for code
    verification_sent_at   = models.DateTimeField(null=True, blank=True)
    otp_attempts           = models.IntegerField(default=0)                # rate-limit

    def __str__(self):
        return f"{self.user.username} ({self.shop.name})"

    def generate_verification_token(self):
        """Create a fresh link-token + 6-digit OTP, save & return both."""
        import secrets
        from django.utils import timezone
        self.verification_token = secrets.token_urlsafe(48)
        self.verification_otp   = f'{secrets.randbelow(1_000_000):06d}'   # 000000-999999
        self.verification_sent_at = timezone.now()
        self.otp_attempts = 0
        self.save()
        return self.verification_token, self.verification_otp

    def is_verification_token_valid(self):
        """Token & OTP both expire after 24 hours."""
        from django.utils import timezone
        from datetime import timedelta
        if not self.verification_sent_at:
            return False
        return timezone.now() - self.verification_sent_at < timedelta(hours=24)

    def is_otp_valid(self):
        """OTP expires after 15 minutes for tighter security."""
        from django.utils import timezone
        from datetime import timedelta
        if not self.verification_sent_at:
            return False
        return timezone.now() - self.verification_sent_at < timedelta(minutes=15)
    

    
# ═════════════════════════════════════════════════════════════
# INVENTORY MODELS
# ═════════════════════════════════════════════════════════════

class Category(models.Model):
    shop        = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='categories')
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
        unique_together = [['shop', 'name']]   # name unique per shop, not globally

    def __str__(self):
        return self.name


class Supplier(models.Model):
    shop       = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='suppliers')
    name       = models.CharField(max_length=200)
    phone      = models.CharField(max_length=20, blank=True)
    email      = models.EmailField(blank=True)
    address    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    shop                = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    name                = models.CharField(max_length=200)
    category            = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    supplier            = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    price               = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity      = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    description         = models.TextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Stock: {self.stock_quantity})"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        return self.stock_quantity == 0


# ═════════════════════════════════════════════════════════════
# SALES MODELS
# ═════════════════════════════════════════════════════════════

class Sale(models.Model):
    DISCOUNT_TYPES = [
        ('amount',  'Amount'),
        ('percent', 'Percent'),
    ]

    shop            = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='sales')
    sale_number     = models.CharField(max_length=20)   # unique per shop, not globally
    created_by      = models.ForeignKey(User, on_delete=models.PROTECT, related_name='sales')
    created_at      = models.DateTimeField(auto_now_add=True)

    subtotal        = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type   = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='amount')
    discount_value  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes           = models.TextField(blank=True)

    class Meta:
        unique_together = [['shop', 'sale_number']]   # unique per shop
        ordering = ['-created_at']

    def __str__(self):
        return f"Sale #{self.sale_number} - Rs. {self.total_amount}"

    def calculate_total(self):
        """Recalculate subtotal, discount, and total from line items."""
        subtotal = sum(item.subtotal for item in self.items.all())
        self.subtotal = subtotal

        if self.discount_type == 'percent':
            self.discount_amount = round(subtotal * self.discount_value / 100, 2)
        else:
            self.discount_amount = self.discount_value

        # Discount can never exceed subtotal
        self.discount_amount = min(self.discount_amount, subtotal)
        self.total_amount    = subtotal - self.discount_amount
        self.save()

    @classmethod
    def generate_sale_number(cls, shop):
        """Generate the next sale number for a specific shop (e.g. SALE-0001)."""
        last = cls.objects.filter(shop=shop).order_by('-id').first()
        next_id = (last.id + 1) if last else 1
        return f"SALE-{next_id:04d}"


class SaleItem(models.Model):
    """Each product line within a sale."""
    sale       = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product    = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')
    quantity   = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    # ↑ Snapshot of the product price at the time of sale.
    #   We DO NOT use product.price directly when reading, because product price
    #   may change later, but past sales must keep their original price.

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"