from django.utils import timezone
from datetime import timedelta
from rest_framework.pagination import PageNumberPagination

def default_loan_due_date():
    return timezone.now().date() + timedelta(days=14)


class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'  # Allow Client-Specified Page Sizes
    max_page_size = 100