from django.urls import path
from .views import *
urlpatterns = [
    path('', SingletonAboutAPIView.as_view(), name='singleton-about'),
    # counts
    path('count/', CountView.as_view(), name='count'),
    # AboutDescription
    path('about-descriptions/', AboutDescriptionListCreateAPIView.as_view(), name='about-description-list-create'),
    path('about-descriptions/<int:pk>/', AboutDescriptionRetrieveUpdateDestroyAPIView.as_view(), name='about-description-detail'),
    # FAQs
    path('faqs/', FAQListCreateAPIView.as_view(), name='faq-list-create'),
    path('faqs/<int:pk>/', FAQRetrieveUpdateDestroyAPIView.as_view(), name='faq-detail'),
    path('faqs_list/', FAQListAPIView.as_view(), name='faq-list-create'), #for customers
    # captions
    path('captions/random/', random_caption, name='random_caption'),
    path('captions/', CaptionListCreateView.as_view(), name='caption-list-create'),
    path('captions/<int:pk>/', CaptionRetrieveUpdateDestroyView.as_view(), name='caption-detail'),
    # Support Descriptions
    path('support-descriptions/', SupportDescriptionListCreateView.as_view(), name='support-description-list-create'),
    path('support-descriptions/<int:pk>/', SupportDescriptionRetrieveUpdateDestroyView.as_view(), name='support-description-detail'),
    path('support-descriptions/active/', ActiveSupportDescriptionListView.as_view(), name='active-support-descriptions'),
    # Welcome Messages
    path('welcome-messages/', WelcomeMessageListCreateView.as_view(), name='welcome-message-list'),
    path('welcome-messages/<str:user_type>/', WelcomeMessageRetrieveUpdateDestroyView.as_view(), name='welcome-message-detail'),

    # User endpoint
    path('user-welcome-message/', UserWelcomeMessageView.as_view(), name='user-welcome-message'),
]

