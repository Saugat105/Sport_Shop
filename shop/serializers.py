from rest_framework import serializers
from .models import Category, Product, Supplier, Sale, SaleItem


# ═════════════════════════════════════════════════════════════
# READ-ONLY SERIALIZERS (used by the API to display data)
# ═════════════════════════════════════════════════════════════

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_low_stock  = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'category', 'category_name',
            'supplier', 'price', 'stock_quantity',
            'low_stock_threshold', 'is_low_stock', 'description',
        ]


# ── Used when READING a sale (shows full item details) ────────
class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal     = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model  = SaleItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price', 'subtotal']


# ═════════════════════════════════════════════════════════════
# WRITE SERIALIZERS (used when CREATING a sale via POS)
# ═════════════════════════════════════════════════════════════

class SaleItemCreateSerializer(serializers.ModelSerializer):
    """Frontend only sends product + quantity. unit_price is taken from product."""
    class Meta:
        model  = SaleItem
        fields = ['product', 'quantity']


class SaleCreateSerializer(serializers.ModelSerializer):
    items = SaleItemCreateSerializer(many=True)

    class Meta:
        model  = Sale
        fields = ['items', 'notes', 'discount_type', 'discount_value']
        extra_kwargs = {
            'notes':          {'required': False, 'allow_blank': True, 'default': ''},
            'discount_type':  {'required': False, 'default': 'amount'},
            'discount_value': {'required': False, 'default': 0},
        }

    # ── Validation ────────────────────────────────────────────
    def validate(self, data):
        # Get the user's shop (multi-tenancy guard)
        user = self.context['request'].user
        if not hasattr(user, 'profile'):
            raise serializers.ValidationError(
                "Your account is not linked to any shop."
            )
        user_shop = user.profile.shop

        items = data.get('items', [])
        if not items:
            raise serializers.ValidationError("Please add at least one product.")

        for item_data in items:
            product  = item_data['product']
            quantity = item_data['quantity']

            # ── CRITICAL SECURITY CHECK ──
            # Ensure the product belongs to the user's shop.
            # Without this, a malicious user could send another shop's product ID
            # in the API request and steal/modify their inventory.
            if product.shop_id != user_shop.id:
                raise serializers.ValidationError(
                    f"Invalid product '{product.name}' — does not belong to your shop."
                )

            if quantity <= 0:
                raise serializers.ValidationError(
                    f"Quantity for '{product.name}' must be greater than 0."
                )
            if product.stock_quantity < quantity:
                raise serializers.ValidationError(
                    f"Not enough stock for '{product.name}'. "
                    f"Available: {product.stock_quantity}, Requested: {quantity}"
                )

        # ── Discount validation ──
        discount_type  = data.get('discount_type', 'amount')
        discount_value = data.get('discount_value', 0)
        if discount_value < 0:
            raise serializers.ValidationError("Discount cannot be negative.")
        if discount_type == 'percent' and discount_value > 100:
            raise serializers.ValidationError("Percentage discount cannot exceed 100%.")

        return data

    # ── Creation ──────────────────────────────────────────────
    def create(self, validated_data):
        from django.db import transaction

        items_data = validated_data.pop('items')
        user       = self.context['request'].user
        shop       = user.profile.shop   # tag the sale with the user's shop

        with transaction.atomic():
            sale = Sale.objects.create(
                shop        = shop,
                sale_number = Sale.generate_sale_number(shop),  # per-shop numbering
                created_by  = user,
                **validated_data
            )

            for item_data in items_data:
                product  = item_data['product']
                quantity = item_data['quantity']

                SaleItem.objects.create(
                    sale       = sale,
                    product    = product,
                    quantity   = quantity,
                    unit_price = product.price,   # snapshot price at time of sale
                )

                # Deduct from stock
                product.stock_quantity -= quantity
                product.save()

            # Recalculate subtotal, discount, and total
            sale.calculate_total()

        return sale


# ═════════════════════════════════════════════════════════════
# READ-ONLY SALE SERIALIZER
# ═════════════════════════════════════════════════════════════

class SaleSerializer(serializers.ModelSerializer):
    items           = SaleItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model  = Sale
        fields = [
            'id', 'sale_number', 'created_by_name',
            'subtotal', 'discount_type', 'discount_value',
            'discount_amount', 'total_amount',
            'created_at', 'items', 'notes',
        ]