from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

from .models import Category, Product, Supplier, Sale
from .serializers import (
    CategorySerializer, ProductSerializer,
    SupplierSerializer, SaleSerializer, SaleCreateSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category', 'supplier').all()
    serializer_class = ProductSerializer

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """GET /api/products/low_stock/ — returns all low stock items"""
        low = [p for p in self.get_queryset() if p.is_low_stock]
        serializer = self.get_serializer(low, many=True)
        return Response(serializer.data)


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.prefetch_related('items__product').all()

    def get_serializer_class(self):
        # Use different serializer for creating vs reading
        if self.action == 'create':
            return SaleCreateSerializer
        return SaleSerializer

    @action(detail=False, methods=['get'])
    def daily_report(self, request):
        """GET /api/sales/daily_report/?date=2024-01-15"""
        date_str = request.query_params.get('date')
        if date_str:
            from datetime import date
            target_date = date.fromisoformat(date_str)
        else:
            target_date = timezone.now().date()

        sales = Sale.objects.filter(created_at__date=target_date)
        total = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        count = sales.count()

        return Response({
            'date': target_date,
            'total_sales': total,
            'transaction_count': count,
            'sales': SaleSerializer(sales, many=True).data
        })

    @action(detail=False, methods=['get'])
    def monthly_report(self, request):
        """GET /api/sales/monthly_report/?year=2024&month=1"""
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))

        sales = Sale.objects.filter(
            created_at__year=year, created_at__month=month
        )
        total = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

        return Response({
            'year': year,
            'month': month,
            'total_revenue': total,
            'transaction_count': sales.count(),
        })