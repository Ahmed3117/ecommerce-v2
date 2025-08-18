from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import FrontEndPage, FrontEndPagePermission

User = get_user_model()


class FrontEndPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FrontEndPage
        fields = ['id', 'title', 'url', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# Legacy serializer removed - using FrontEndPagePermissionSerializer instead


class FrontEndPagePermissionSerializer(serializers.ModelSerializer):
    pages = FrontEndPageSerializer(many=True, read_only=True)
    page_ids = serializers.PrimaryKeyRelatedField(
        queryset=FrontEndPage.objects.all(),
        source='pages',
        write_only=True,
        many=True
    )
    
    class Meta:
        model = FrontEndPagePermission
        fields = ['id', 'user', 'pages', 'page_ids', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AssignFrontEndPagesSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    frontend_page_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        help_text="List of frontend page IDs to assign to the user"
    )
    
    def validate_user_id(self, value):
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist.")
        return value
    
    def validate_frontend_page_ids(self, value):
        # Check if all frontend pages exist
        existing_ids = set(FrontEndPage.objects.filter(id__in=value).values_list('id', flat=True))
        invalid_ids = set(value) - existing_ids
        
        if invalid_ids:
            raise serializers.ValidationError(f"Frontend pages with IDs {list(invalid_ids)} do not exist.")
        
        return value
