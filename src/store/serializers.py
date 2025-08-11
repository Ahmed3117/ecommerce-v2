from rest_framework import serializers

from accounts.models import User
from .models import StoreRequest, Store, StoreReporting


class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'name', 'email', 'phone']

class StoreRequestSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    image = serializers.ImageField(required=False, allow_null=True)
    national_id_image = serializers.ImageField(required=True)
    
    class Meta:
        model = StoreRequest
        fields = '__all__'
        read_only_fields = ['status', 'date_added', 'date_updated', 'refuse_reason']

    def create(self, validated_data):
        # Set user if authenticated, otherwise leave as None
        if 'request' in self.context and self.context['request'].user.is_authenticated:
            validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class StoreSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(read_only=True)
    image = serializers.ImageField(required=False, allow_null=True)
    national_id_image = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = Store
        fields = '__all__'



class StoreReportingSerializer(serializers.ModelSerializer):
    store = StoreSerializer(read_only=True)
    store_id = serializers.PrimaryKeyRelatedField(
        source='store',
        queryset=Store.objects.all(),
        write_only=True
    )
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = StoreReporting
        fields = ['id', 'store', 'store_id', 'user', 'text', 'date', 'is_handled']
        read_only_fields = ['user', 'date', 'is_handled', 'store']