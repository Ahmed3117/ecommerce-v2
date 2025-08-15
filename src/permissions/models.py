from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AllowedEndpoint(models.Model):
    """Model to store allowed endpoints with URL and HTTP method"""
    url = models.CharField(max_length=255, help_text="API endpoint URL")
    method = models.CharField(
        max_length=10, 
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('PATCH', 'PATCH'),
            ('DELETE', 'DELETE'),
        ],
        help_text="HTTP method"
    )
    
    class Meta:
        unique_together = ('url', 'method')
        verbose_name = "Allowed Endpoint"
        verbose_name_plural = "Allowed Endpoints"
    
    def __str__(self):
        return f"{self.method} {self.url}"


class AllowedEndpointGroup(models.Model):
    """Model to group multiple endpoints together"""
    name = models.CharField(max_length=100, unique=True, help_text="Group name")
    description = models.TextField(blank=True, help_text="Group description")
    allowed_endpoints = models.ManyToManyField(
        AllowedEndpoint, 
        related_name='groups',
        help_text="Endpoints included in this group"
    )
    
    class Meta:
        verbose_name = "Allowed Endpoint Group"
        verbose_name_plural = "Allowed Endpoint Groups"
    
    def __str__(self):
        return self.name


class UserPermission(models.Model):
    """Model to assign permissions to users either directly or through groups"""
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='user_permission'
    )
    allowed_endpoints = models.ManyToManyField(
        AllowedEndpoint, 
        blank=True,
        help_text="Direct endpoint permissions (used if no group is assigned)"
    )
    group = models.ForeignKey(
        AllowedEndpointGroup, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Permission group (takes precedence over direct permissions)"
    )
    
    class Meta:
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"
    
    def __str__(self):
        return f"Permissions for {self.user.email}"
    
    def get_allowed_endpoints(self):
        """Get the effective allowed endpoints for this user"""
        if self.group:
            # If user has a group, use group permissions
            return self.group.allowed_endpoints.all()
        else:
            # Otherwise, use direct permissions
            return self.allowed_endpoints.all()
