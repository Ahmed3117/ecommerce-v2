from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from accounts.models import GOVERNMENT_CHOICES, User

class StoreRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('refused', 'Refused'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='store_requests'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    image = models.ImageField(
        upload_to='store_requests/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    national_id_image = models.ImageField(
        upload_to='stores/national_ids/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png','webp'])]
    )
    store_name = models.CharField(max_length=100,null=True, blank=True)  # Optional for requests
    government = models.CharField(choices=GOVERNMENT_CHOICES, max_length=2, null=True, blank=True)
    address = models.TextField()
    phone1 = models.CharField(max_length=20,null=True, blank=True)
    phone2 = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20, null=True, blank=True)
    facebook_link = models.URLField(null=True, blank=True)
    telegram_link = models.URLField(null=True, blank=True)
    instagram_link = models.URLField(null=True, blank=True)
    youtube_link = models.URLField(null=True, blank=True)
    tiktok_link = models.URLField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    date_added = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    refuse_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Store Request from {self.first_name} {self.last_name}"
    class Meta:
        ordering = ['-date_added']  


class Store(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        # limit_choices_to={'user_type': 'store'},
        related_name='store'
    )
    store_name = models.CharField(max_length=100 , null=True , blank=True) # Store name
    image = models.ImageField(
        upload_to='stores/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png','webp'])]
    )
    national_id_image = models.ImageField(
        upload_to='stores/national_ids/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png','webp'])]
    )
    government = models.CharField(choices=GOVERNMENT_CHOICES, max_length=2, null=True, blank=True)
    address = models.TextField()
    phone1 = models.CharField(max_length=20)
    phone2 = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20, null=True, blank=True)
    facebook_link = models.URLField(null=True, blank=True)
    telegram_link = models.URLField(null=True, blank=True)
    instagram_link = models.URLField(null=True, blank=True)
    youtube_link = models.URLField(null=True, blank=True)
    tiktok_link = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now) 

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']


class StoreReporting(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='store_reports'
    )
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    is_handled = models.BooleanField(default=False)

    def __str__(self):
        return f"Report on {self.store.name} by {self.user.username}"