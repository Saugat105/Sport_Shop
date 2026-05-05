from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import Product, Category, Supplier, Shop, UserProfile


# ═════════════════════════════════════════════════════════════
# PRODUCT FORM
# ═════════════════════════════════════════════════════════════

class ProductForm(forms.ModelForm):
    """
    Edits/adds a Product. Filters Category and Supplier dropdowns
    so users only see items belonging to their own shop.
    """

    class Meta:
        model = Product
        fields = [
            'name', 'category', 'supplier',
            'price', 'cost_price',
            'stock_quantity', 'low_stock_threshold',
            'description',
        ]

    def __init__(self, *args, **kwargs):
        # Pull `shop` out before calling super (it's not a real form field)
        shop = kwargs.pop('shop', None)
        super().__init__(*args, **kwargs)

        if shop is not None:
            self.fields['category'].queryset = Category.objects.filter(shop=shop)
            self.fields['supplier'].queryset = Supplier.objects.filter(shop=shop)
        else:
            # Safety net: if no shop passed, show empty querysets
            self.fields['category'].queryset = Category.objects.none()
            self.fields['supplier'].queryset = Supplier.objects.none()


# ═════════════════════════════════════════════════════════════
# SIGNUP FORM — creates User + Shop + UserProfile together
# ═════════════════════════════════════════════════════════════

class SignupForm(UserCreationForm):
    # ── Personal info ──
    first_name = forms.CharField(
        max_length=50, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'First name',
        })
    )
    last_name = forms.CharField(
        max_length=50, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Last name',
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 'placeholder': 'name@example.com',
        })
    )

    # ── Shop info (NEW — signup creates a new shop too) ──
    shop_name = forms.CharField(
        max_length=200, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Himalayan Sport Shop',
        })
    )
    shop_address = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Pokhara, Nepal',
        })
    )
    shop_phone = forms.CharField(
        max_length=20, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+977-xxx-xxxx',
        })
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'shop_name', 'shop_address', 'shop_phone',
            'password1', 'password2',
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Choose a username',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style password fields (UserCreationForm doesn't style them by default)
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a strong password',
        })
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repeat password',
        })

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        """
        Saves three things in order:
        1. The User
        2. A new Shop owned by that user
        3. A UserProfile linking the User to the Shop with role='owner'
        """
        user = super().save(commit=False)
        user.email      = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data.get('last_name', '')

        if commit:
            user.save()

            # Create the shop
            shop = Shop.objects.create(
                name       = self.cleaned_data['shop_name'],
                owner_name = user.get_full_name() or user.username,
                address    = self.cleaned_data.get('shop_address', ''),
                phone      = self.cleaned_data.get('shop_phone', ''),
                email      = user.email,
            )

            # Link user to shop as OWNER
            UserProfile.objects.create(user=user, shop=shop, role='owner')

        return user


# ═════════════════════════════════════════════════════════════
# TEAM INVITE FORM — owner adds staff/admin to their shop
# ═════════════════════════════════════════════════════════════

class TeamMemberForm(forms.Form):
    """
    Used by shop owners to add new staff/admin to their shop.
    The owner specifies the new user's username, email, role, and password.
    """
    username = forms.CharField(
        max_length=150, required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'New staff username',
        })
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'staff@example.com (optional)',
        })
    )
    role = forms.ChoiceField(
        choices=[('staff', 'Staff'), ('admin', 'Admin')],
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='staff',
    )
    password = forms.CharField(
        min_length=6, required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Temporary password (share with staff)',
        })
    )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username