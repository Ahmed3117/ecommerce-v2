from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from accounts.models import User
from .models import StoreRequest, Store, StoreReporting
from .serializers import StoreRequestSerializer, StoreSerializer, StoreReportingSerializer
from django.shortcuts import get_object_or_404



class StoreRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = StoreRequestSerializer
    permission_classes = [permissions.AllowAny]  # Changed from IsAuthenticated to AllowAny
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'government']
    search_fields = ['store_name', 'email', 'first_name', 'last_name', 'phone1', 'phone2']

    def get_queryset(self):
        if self.request.user.is_staff:
            return StoreRequest.objects.all().order_by('-date_added')
        if self.request.user.is_authenticated:
            return StoreRequest.objects.filter(user=self.request.user).order_by('-date_added')
        return StoreRequest.objects.none()  # Unauthenticated users can't list requests

    def create(self, request, *args, **kwargs):
        # For authenticated users, check if they already have a request
        if request.user.is_authenticated:
            existing_request = StoreRequest.objects.filter(user=request.user).first()
            if existing_request:
                serializer = self.get_serializer(existing_request)
                return Response(
                    {
                        'message': 'You already have a pending store request',
                        'your_request': serializer.data
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Proceed with normal creation
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()  # user will be None

class StoreRequestRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = StoreRequestSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return StoreRequest.objects.all()
        if self.request.user.is_authenticated:
            return StoreRequest.objects.filter(user=self.request.user)
        return StoreRequest.objects.none()

class ApproveStoreRequestView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        store_request = get_object_or_404(StoreRequest, pk=pk)
        
        if store_request.status != 'pending':
            return Response(
                {'error': 'Request has already been processed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create user if request was from unauthenticated user
        if not store_request.user:
            # Create new user with store type
            user = User.objects.create_user(
                username=store_request.email,
                email=store_request.email,
                first_name=store_request.first_name,
                last_name=store_request.last_name,
                user_type='store'
            )
            # You might want to set a temporary password and send it via email
        else:
            user = store_request.user
            user.user_type = 'store'
            user.save()
        
        # Create the store
        store = Store.objects.create(
            user=user,
            store_name=store_request.store_name,
            image=store_request.image,
            national_id_image=store_request.national_id_image,
            government=store_request.government,
            address=store_request.address,
            phone1=store_request.phone1,
            phone2=store_request.phone2,
            email=store_request.email,
            whatsapp_number=store_request.whatsapp_number,
            facebook_link=store_request.facebook_link,
            telegram_link=store_request.telegram_link,
            instagram_link=store_request.instagram_link,
            youtube_link=store_request.youtube_link,
            tiktok_link=store_request.tiktok_link,
        )
        
        # Update request status
        store_request.status = 'accepted'
        store_request.save()
        
        return Response(
            {'message': 'Store request approved and store created successfully'},
            status=status.HTTP_200_OK
        )

class RejectStoreRequestView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        store_request = get_object_or_404(StoreRequest, pk=pk)
        refuse_reason = request.data.get('refuse_reason', '')
        
        if store_request.status != 'pending':
            return Response(
                {'error': 'Request has already been processed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        store_request.status = 'refused'
        store_request.refuse_reason = refuse_reason
        store_request.save()
        
        return Response(
            {'message': 'Store request rejected successfully'},
            status=status.HTTP_200_OK
        )

class StoreListCreateView(generics.ListCreateAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['government',]
    search_fields = ['store_name', 'government', 'address', 'phone1', 'phone2', 'email']

class StoreRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = Store.objects.all()

class StoreReportingListCreateView(generics.ListCreateAPIView):
    serializer_class = StoreReportingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['store','is_handled']
    search_fields = ['store__store_name', 'user__username']

    def get_queryset(self):
        if self.request.user.is_staff:
            return StoreReporting.objects.all().order_by('-date')
        return StoreReporting.objects.filter(user=self.request.user).order_by('-date')

    def perform_create(self, serializer):
        # Get store instance from the provided ID
        store_id = self.request.data.get('store_id')
        print(f"Store ID: {store_id}")
        store = get_object_or_404(Store, id=store_id)
        
        serializer.save(
            user=self.request.user,
            store=store
        )

class StoreReportingRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = StoreReportingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return StoreReporting.objects.all()
        return StoreReporting.objects.filter(user=self.request.user)