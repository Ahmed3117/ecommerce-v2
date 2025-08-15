from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated,IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from accounts.utils import send_whatsapp_massage
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import random
from .serializers import ChangePasswordSerializer, UserAddressSerializer, UserDetailSerializer, UserProfileImageCreateSerializer, UserProfileImageSerializer, UserProfileSerializer, UserSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from .models import User, UserAddress, UserProfileImage
from django.contrib.auth import update_session_auth_hash
from rest_framework import generics
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count
from permissions import IsAdminOrHasEndpointPermission


def get_user_permissions(user):
    """Helper function to get user permissions"""
    try:
        # Import here to avoid app loading issues
        from permissions.models import UserPermission
        user_permission = UserPermission.objects.get(user=user)
        allowed_endpoints = user_permission.get_allowed_endpoints()
        
        permissions = []
        for endpoint in allowed_endpoints:
            permissions.append({
                'url': endpoint.url,
                'method': endpoint.method
            })
        
        return permissions
    except Exception:
        # UserPermission.DoesNotExist or import error
        return []  # Return empty if permissions app not available or user has no permissions


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        user_data = serializer.data
        user_data['is_admin'] = user.is_staff or user.is_superuser
        
        # Get user permissions (will be empty for new users)
        user_permissions = get_user_permissions(user)
        user_data['permissions'] = user_permissions
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user_data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def signin(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        refresh = RefreshToken.for_user(user)
        # Pass the request object into the serializer's context
        serializer = UserSerializer(user, context={'request': request})
        user_data = serializer.data
        user_data['is_admin'] = user.is_staff or user.is_superuser
        
        # Get user permissions
        user_permissions = get_user_permissions(user)
        user_data['permissions'] = user_permissions

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user_data
        })
    except Exception as e:
        return Response({'error': f'Token generation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    if serializer.is_valid():
        phone = serializer.validated_data['phone']
        try:
            user = User.objects.get(phone=phone)
            otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user.otp = otp
            user.otp_created_at = timezone.now()
            user.save()
            
            # Send OTP via WhatsApp instead of email
            req_send = send_whatsapp_massage(
                massage=f'Your PIN code is {otp}',
                phone_number=f'{phone}'
            )
            
            if req_send:  # Assuming the function returns True on success
                return Response({'message': 'OTP sent to your phone via WhatsApp'})
            else:
                return Response({'error': 'Failed to send OTP via WhatsApp'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if serializer.is_valid():
        phone = serializer.validated_data['phone']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(phone=phone, otp=otp)
            if user.otp_created_at < timezone.now() - timedelta(minutes=10):
                return Response({'error': 'OTP expired'}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(new_password)
            user.otp = None
            user.otp_created_at = None
            user.save()
            
            return Response({'message': 'Password reset successful'})
        except User.DoesNotExist:
            return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class UpdateUserData(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class GetUserData(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class UserAddressListCreateView(generics.ListCreateAPIView):
    serializer_class = UserAddressSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_default']
    search_fields = ['name', 'email', 'phone', 'address']

    def get_queryset(self):
        return UserAddress.objects.filter(user=self.request.user).order_by('-is_default', '-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class UserAddressRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserAddress.objects.filter(user=self.request.user)

class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        
        # Verify old password
        if not user.check_password(old_password):
            return Response(
                {'error': 'Old password is incorrect'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        
        return Response(
            {'message': 'Password updated successfully'}, 
            status=status.HTTP_200_OK
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#^ ---------------------------------------------------- Dashboard ---------------------------- ^#

@api_view(['POST'])
# @permission_classes([IsAdminUser])
def create_admin_user(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save(is_staff=True, is_superuser=True)
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': serializer.data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserCreateAPIView(APIView):
    permission_classes = [IsAdminOrHasEndpointPermission]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserUpdateAPIView(APIView):
    permission_classes = [IsAdminOrHasEndpointPermission]

    def patch(self, request, username):  # Changed from pk to username
        try:
            user = User.objects.get(username=username)  # Changed to use username
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserDeleteAPIView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class UserProfileImageListCreateView(generics.ListCreateAPIView):
    queryset = UserProfileImage.objects.all()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserProfileImageCreateSerializer
        return UserProfileImageSerializer

class UserProfileImageRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserProfileImage.objects.all()
    serializer_class = UserProfileImageSerializer
    # permission_classes = [IsAdminUser]


# user analysis

class AdminUserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    # permission_classes = [IsAdminUser]
    queryset = User.objects.prefetch_related(
        'pills',
        'loved_products'
    ).order_by('-created_at')
    
    filter_backends = [SearchFilter, OrderingFilter,DjangoFilterBackend]
    ordering_fields = [
        'created_at', 
        'cart_items_count', 
        'loved_count'
    ]
    search_fields = ['username', 'name', 'email', 'phone','address', 'government', 'city']
    filterset_fields = ['is_staff', 'is_superuser','year', 'government']


class AdminUserDetailView(generics.RetrieveAPIView):
    serializer_class = UserDetailSerializer
    # permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    lookup_field = 'pk'






