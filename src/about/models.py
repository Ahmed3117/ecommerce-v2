from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import USER_TYPE_CHOICES


class About(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()
    image = models.ImageField(upload_to='about_images/', null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    phone1 = models.CharField(max_length=20, null=True, blank=True)
    phone2 = models.CharField(max_length=20, null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20, null=True, blank=True)

    facebook_link = models.URLField(null=True, blank=True)
    telegram_link = models.URLField(null=True, blank=True)
    instagram_link = models.URLField(null=True, blank=True)
    youtube_link = models.URLField(null=True, blank=True)
    tiktok_link = models.URLField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.pk and About.objects.exists():
            raise ValidationError("Only one About instance is allowed.")
        super().save(*args, **kwargs)


class AboutDescription(models.Model):
    about = models.ForeignKey(About, on_delete=models.CASCADE, related_name='descriptions')
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.about.title} - {self.order}"

class SupportDescription(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Support Description"
        verbose_name_plural = "Support Descriptions"
        ordering = ['-created_at']

class Count(models.Model):
    subscribers_count = models.PositiveIntegerField(default=0)
    doctors_count = models.PositiveIntegerField(default=0)
    students_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "Global Count Metrics"

    def save(self, *args, **kwargs):
        if not self.pk and Count.objects.exists():
            raise ValidationError("Only one Count instance is allowed.")
        super().save(*args, **kwargs)

class Caption(models.Model):
    caption = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True , null=True)

    def __str__(self):
        return self.caption

class WelcomeMessage(models.Model):
    text = models.TextField()
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        unique=True  # Ensures only one message per user type
    )

    def __str__(self):
        return f"Welcome message for {self.user_type}"


#------------- FAQ -------------#

class FAQ(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    file = models.FileField(upload_to='faq_files/', null=True, blank=True)
    video_url = models.URLField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title