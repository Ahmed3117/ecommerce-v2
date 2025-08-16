from rest_framework.permissions import BasePermission
from django.conf import settings


class IsAdminOrHasEndpointPermission(BasePermission):
    """
    Custom permission class that allows access if:
    1. User is a superuser (full access)
    2. User is staff AND has specific endpoint permission
    3. User is staff with no UserPermission record (default allow for backward compatibility)
    """
    
    def has_permission(self, request, view):
        # Allow access if user is not authenticated (handled by authentication classes)
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers have full access
        if request.user.is_superuser:
            return True
        
        # Non-staff users are denied
        if not request.user.is_staff:
            return False
        
        # For staff users, check endpoint permissions
        return self._check_endpoint_permission(request)
    
    def _check_endpoint_permission(self, request):
        """Check if the staff user has permission for this specific endpoint"""
        try:
            # Import here to avoid circular imports and app loading issues
            from .models import UserPermission
            
            user_permission = UserPermission.objects.get(user=request.user)
            allowed_endpoints = user_permission.get_allowed_endpoints()
            
            # Get current request info
            current_url = request.path
            current_method = request.method
            
            # Check if user has permission for this endpoint
            for endpoint in allowed_endpoints:
                if self._url_matches(endpoint.url, current_url) and endpoint.method == current_method:
                    return True
            
            return False
            
        except Exception:
            # Import error or UserPermission.DoesNotExist or any other error
            # If no UserPermission exists, allow access (backward compatibility)
            # You can change this to False if you want to require explicit permissions
            return True
    
    def _url_matches(self, pattern_url, request_url):
        """
        Check if the request URL matches the pattern URL.
        This supports both exact matches and basic wildcard patterns.
        """
        # Exact match
        if pattern_url == request_url:
            return True
        
        # Wildcard support: /api/products/* matches /api/products/123/
        if pattern_url.endswith('*'):
            pattern_base = pattern_url[:-1]  # Remove the *
            return request_url.startswith(pattern_base)
        
        # API parameter matching: /api/products/{id}/ matches /api/products/123/
        if '{' in pattern_url and '}' in pattern_url:
            return self._match_parameterized_url(pattern_url, request_url)
        
        return False
    
    def _match_parameterized_url(self, pattern_url, request_url):
        """
        Match URLs with parameters like /api/products/{id}/
        """
        pattern_parts = pattern_url.split('/')
        request_parts = request_url.split('/')
        
        if len(pattern_parts) != len(request_parts):
            return False
        
        for pattern_part, request_part in zip(pattern_parts, request_parts):
            # Skip parameter parts (enclosed in {})
            if pattern_part.startswith('{') and pattern_part.endswith('}'):
                continue
            # Exact match required for non-parameter parts
            if pattern_part != request_part:
                return False
        
        return True


class IsStaffWithEndpointPermission(BasePermission):
    """
    Stricter permission class that requires explicit endpoint permissions for all staff users.
    Use this if you want to enforce permissions for all staff users.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers have full access
        if request.user.is_superuser:
            return True
        
        # Non-staff users are denied
        if not request.user.is_staff:
            return False
        
        # For staff users, always check endpoint permissions
        try:
            # Import here to avoid circular imports and app loading issues
            from .models import UserPermission
            
            user_permission = UserPermission.objects.get(user=request.user)
            allowed_endpoints = user_permission.get_allowed_endpoints()
            
            current_url = request.path
            current_method = request.method
            
            for endpoint in allowed_endpoints:
                if self._url_matches(endpoint.url, current_url) and endpoint.method == current_method:
                    return True
            
            return False
            
        except Exception:
            # No permissions defined = no access
            return False
    
    def _url_matches(self, pattern_url, request_url):
        """Same URL matching logic as above"""
        if pattern_url == request_url:
            return True
        
        if pattern_url.endswith('*'):
            pattern_base = pattern_url[:-1]
            return request_url.startswith(pattern_base)
        
        if '{' in pattern_url and '}' in pattern_url:
            return self._match_parameterized_url(pattern_url, request_url)
        
        return False
    
    def _match_parameterized_url(self, pattern_url, request_url):
        """Same parameterized URL matching logic as above"""
        pattern_parts = pattern_url.split('/')
        request_parts = request_url.split('/')
        
        if len(pattern_parts) != len(request_parts):
            return False
        
        for pattern_part, request_part in zip(pattern_parts, request_parts):
            if pattern_part.startswith('{') and pattern_part.endswith('}'):
                continue
            if pattern_part != request_part:
                return False
        
        return True


# Convenience function to easily apply permissions to views
def require_endpoint_permission(view_func):
    """
    Decorator to easily apply endpoint permissions to function-based views
    Usage:
    
    @api_view(['GET'])
    @require_endpoint_permission
    def my_view(request):
        return Response({'message': 'Hello'})
    """
    from rest_framework.decorators import permission_classes
    
    @permission_classes([IsAdminOrHasEndpointPermission])
    def wrapper(*args, **kwargs):
        return view_func(*args, **kwargs)
    
    return wrapper
