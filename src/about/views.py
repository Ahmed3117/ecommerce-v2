
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django_filters.rest_framework import DjangoFilterBackend
import rest_framework.filters as rest_filters
from django.http import Http404
from about.models import FAQ, About, AboutDescription, Caption, Count, SupportDescription, WelcomeMessage
from about.serializers import AboutDescriptionSerializer, AboutSerializer, CaptionSerializer, CountSerializer, FAQSerializer, SupportDescriptionSerializer, WelcomeMessageSerializer, WelcomeMessageUpdateSerializer
import random
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
# CRUD for About
class SingletonAboutAPIView(APIView):
    """
    GET: Retrieve the single About object with its descriptions.
    PUT/PATCH: Update the single About object.
    POST: Create it only if it doesn't exist (optional).
    """

    def get_object(self):
        return About.objects.first()

    def get(self, request):
        about = self.get_object()
        if not about:
            return Response({"detail": "About content not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AboutSerializer(about, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        if About.objects.exists():
            return Response({"detail": "About already exists."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = AboutSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        about = self.get_object()
        if not about:
            return self.post(request)
        serializer = AboutSerializer(about, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        about = self.get_object()
        if not about:
            return Response({"detail": "About not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AboutSerializer(about, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# CRUD for AboutDescription
class AboutDescriptionListCreateAPIView(generics.ListCreateAPIView):
    queryset = AboutDescription.objects.all()
    serializer_class = AboutDescriptionSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_fields = ['about', 'is_active']
    search_fields = ['description','title']


class AboutDescriptionRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AboutDescription.objects.all()
    serializer_class = AboutDescriptionSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def random_caption(request):
    count = Caption.objects.filter(is_active = True).count()
    if count == 0:
        return Response({'error': 'No captions available'}, status=404)
    
    random_index = random.randint(0, count - 1)
    random_caption = Caption.objects.filter(is_active = True)[random_index]
    serializer = CaptionSerializer(random_caption)
    return Response(serializer.data)

class ActiveSupportDescriptionListView(generics.ListAPIView):
    serializer_class = SupportDescriptionSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return SupportDescription.objects.filter(is_active=True).order_by('-created_at')
    



class UserWelcomeMessageView(generics.RetrieveAPIView):
    serializer_class = WelcomeMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Get the welcome message for the current user's type
        user_type = self.request.user.user_type
        message = WelcomeMessage.objects.filter(user_type=user_type).first()

        if not message:
            raise Http404("No welcome message found for your user type")

        return message


#^ < ==========================Dashboard endpoints========================== >

class FAQListCreateAPIView(generics.ListCreateAPIView):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['title', 'description']

class FAQRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    
class SupportDescriptionListCreateView(generics.ListCreateAPIView):
    queryset = SupportDescription.objects.all()
    serializer_class = SupportDescriptionSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['title', 'description']
    # permission_classes = [IsAdminUser]

class SupportDescriptionRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SupportDescription.objects.all()
    serializer_class = SupportDescriptionSerializer
    # permission_classes = [IsAdminUser]
    lookup_field = 'pk'

class CountView(generics.RetrieveUpdateAPIView):
    serializer_class = CountSerializer

    def get_object(self):
        obj, _ = Count.objects.get_or_create()
        return obj


class CaptionListCreateView(generics.ListCreateAPIView):
    queryset = Caption.objects.all()
    serializer_class = CaptionSerializer
    permission_classes = [IsAdminUser]  # Only admins can create/see all
    

class CaptionRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Caption.objects.all()
    serializer_class = CaptionSerializer
    permission_classes = [IsAdminUser]  # Only admins can modify
    lookup_field = 'pk'

class WelcomeMessageListCreateView(generics.ListCreateAPIView):
    serializer_class = WelcomeMessageSerializer
    # permission_classes = [IsAdminUser]

    def get_queryset(self):
        return WelcomeMessage.objects.all()

    def create(self, request, *args, **kwargs):
        user_type = request.data.get('user_type')
        if not user_type:
            return Response(
                {"error": "user_type is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if message for this user type already exists
        existing_message = WelcomeMessage.objects.filter(user_type=user_type).first()

        if existing_message:
            # Update existing message
            serializer = WelcomeMessageUpdateSerializer(
                existing_message,
                data={'text': request.data.get('text')},
                partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Create new message
            return super().create(request, *args, **kwargs)

class WelcomeMessageRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WelcomeMessage.objects.all()
    serializer_class = WelcomeMessageSerializer
    # permission_classes = [IsAdminUser]
    lookup_field = 'user_type'  # Use user_type as the lookup field instead of id

# CRUD for FAQ
class FAQListAPIView(generics.ListAPIView):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['title', 'description']







