from django.contrib.auth.models import AbstractUser
from django.db import models

GOVERNMENT_CHOICES = [
    ('1', 'Cairo'),
    ('2', 'Alexandria'),
    ('3', 'Kafr El Sheikh'),
    ('4', 'Dakahleya'),
    ('5', 'Sharkeya'),
    ('6', 'Gharbeya'),
    ('7', 'Monefeya'),
    ('8', 'Qalyubia'),
    ('9', 'Giza'),
    ('10', 'Bani-Sweif'),
    ('11', 'Fayoum'),
    ('12', 'Menya'),
    ('13', 'Assiut'),
    ('14', 'Sohag'),
    ('15', 'Qena'),
    ('16', 'Luxor'),
    ('17', 'Aswan'),
    ('18', 'Red Sea'),
    ('19', 'Behera'),
    ('20', 'Ismailia'),
    ('21', 'Suez'),
    ('22', 'Port-Said'),
    ('23', 'Damietta'),
    ('24', 'Marsa Matrouh'),
    ('25', 'Al-Wadi Al-Gadid'),
    ('26', 'North Sinai'),
    ('27', 'South Sinai'),
]

USER_TYPE_CHOICES = [
        ('student', 'Student'),
        ('parent', 'Parent'),
        ('store', 'Store'),
    ]
    
YEAR_CHOICES = [
        ('first-secondary', 'First Secondary'),
        ('second-secondary', 'Second Secondary'),
        ('third-secondary', 'Third Secondary'),
    ]

DIVISION_CHOICES = [
    ('عام', 'عام'),
    ('علمى', 'علمى'),
    ('أدبي', 'أدبي'),
    ('علمى علوم', 'علمى علوم'),
    ('علمى رياضة', 'علمى رياضة'),

]

class UserProfileImage(models.Model):
    image = models.ImageField(upload_to='profile_images/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile Image {self.id}"
    
    class Meta:
        ordering = ['-created_at'] 


class User(AbstractUser):
    name = models.CharField(max_length=100)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True, max_length=254)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default="student", null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    phone2 = models.CharField(max_length=20, null=True, blank=True)
    parent_phone = models.CharField(max_length=20, null=True, blank=True, help_text="Only applicable for students")
    year = models.CharField(
        max_length=20,
        choices=YEAR_CHOICES,
        null=True,
        blank=True,
        help_text="Only applicable for students"
    )
    division = models.CharField(
        max_length=20,
        choices=DIVISION_CHOICES,
        null=True,
        blank=True
    )
    government = models.CharField(choices=GOVERNMENT_CHOICES, max_length=2, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    user_profile_image = models.ForeignKey(
        UserProfileImage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    created_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)

    def __str__(self):
        return self.name if self.name else self.username
    
    class Meta:
        ordering = ['-created_at']


class UserAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    name = models.CharField(max_length=150,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    phone2 = models.CharField(max_length=20, null=True, blank=True)
    government = models.CharField(choices=GOVERNMENT_CHOICES, max_length=2,null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=255,null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.address}"

    def save(self, *args, **kwargs):
        # If this address is being set as default
        if self.is_default:
            # Get all other addresses for this user
            other_addresses = UserAddress.objects.filter(user=self.user)
            
            # If this is an existing instance, exclude it from the update
            if self.pk:
                other_addresses = other_addresses.exclude(pk=self.pk)
            
            # Update all other addresses to not be default
            other_addresses.update(is_default=False)
        
        # If this is the first address being created for the user, set it as default
        elif not UserAddress.objects.filter(user=self.user).exists():
            self.is_default = True
            
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'User Addresses'
        ordering = ['-is_default', '-created_at']








