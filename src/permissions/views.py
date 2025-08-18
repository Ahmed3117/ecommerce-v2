from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import FrontEndPage, FrontEndPagePermission
from .serializers import (
    FrontEndPageSerializer, 
    FrontEndPagePermissionSerializer,
    AssignFrontEndPagesSerializer
)

User = get_user_model()


class FrontEndPageListView(generics.ListAPIView):
    """List all available frontend pages"""
    queryset = FrontEndPage.objects.all()
    serializer_class = FrontEndPageSerializer
    permission_classes = []  # Allow public access to see available pages
    
    def get_permissions(self):
        # Import here to avoid app loading issues
        from .permissions import IsAdminOrHasEndpointPermission
        return [IsAdminOrHasEndpointPermission()]


@api_view(['POST'])
def assign_frontend_pages(request):
    """
    Assign frontend pages to a user.
    This will replace all existing frontend page permissions for the user.
    
    Expected payload:
    {
        "user_id": 1,
        "frontend_page_ids": [1, 2, 3]
    }
    """
    # Check permissions manually
    from .permissions import IsAdminOrHasEndpointPermission
    permission = IsAdminOrHasEndpointPermission()
    # if not permission.has_permission(request, None):
    #     return Response({
    #         'success': False,
    #         'error': 'Permission denied'
    #     }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = AssignFrontEndPagesSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user_id = serializer.validated_data['user_id']
    frontend_page_ids = serializer.validated_data['frontend_page_ids']
    
    try:
        user = User.objects.get(id=user_id)
        
        with transaction.atomic():
            # Get or create the FrontEndPagePermission for this user
            permission, created = FrontEndPagePermission.objects.get_or_create(user=user)
            
            # Clear existing pages
            permission.pages.clear()
            
            # Add new pages
            frontend_pages = FrontEndPage.objects.filter(id__in=frontend_page_ids)
            permission.pages.add(*frontend_pages)
        
        # Get the updated permission to return
        permission = FrontEndPagePermission.objects.get(user=user)
        serializer = FrontEndPagePermissionSerializer(permission)
        
        return Response({
            'success': True,
            'message': f'Successfully assigned {len(frontend_page_ids)} frontend pages to user {user.email}',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_user_frontend_pages(request, user_id):
    """Get frontend pages for a specific user (simplified endpoint)"""
    # Check permissions manually
    from .permissions import IsAdminOrHasEndpointPermission
    permission = IsAdminOrHasEndpointPermission()
    # if not permission.has_permission(request, None):
    #     return Response({
    #         'success': False,
    #         'error': 'Permission denied'
    #     }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
        
        try:
            permission = FrontEndPagePermission.objects.get(user=user)
            pages = permission.pages.all()
            
            # Return just the frontend page data
            pages_data = []
            for page in pages:
                pages_data.append({
                    'id': page.id,
                    'title': page.title,
                    'url': page.url
                })
        except FrontEndPagePermission.DoesNotExist:
            # No permissions found
            pages_data = []
        
        return Response({
            'success': True,
            'user_id': user_id,
            'frontend_pages': pages_data
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
