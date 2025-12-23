from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import (
    AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, ExtendDueDateSerializer,
    TopActiveMembersSerializer
)
from rest_framework.decorators import action
from django.utils import timezone
from .tasks import send_loan_notification
from django.db.models import F, Count, Q
from datetime import timedelta
import logging
from django.db import connection

logger = logging.getLogger(__name__)

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related('author').order_by('title')

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        logger.info(f"No of Queries: {len(connection.queries)}")
        return response


    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['get'], url_path='top-active')
    def top_active_members(self, request):
        top_active_members = Member.objects.select_related('user').annotate(
            active_loans=Count('loans', filter=Q(loans__is_returned=False))
        ).filter(active_loans__gt=0).order_by(
            '-active_loans', 'user__username'
        )[:5]

        serializer = TopActiveMembersSerializer(top_active_members, many=True)
        return Response(serializer.data)

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'])
    def extend_due_date(self, request, pk=None):
        serializer = ExtendDueDateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors)

        loan = self.get_object()

        if loan.is_returned:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        if loan.due_date < timezone.now().date():
            return Response({'error': 'You can not extend an overdue loan.'}, status=status.HTTP_400_BAD_REQUEST)

        loan.due_date = F('due_date') + timedelta(days=serializer.validated_data['additional_days'])
        loan.save(update_fields=['due_date'])
        loan.refresh_from_db(fields=['due_date'])

        loan_serializer = self.get_serializer(loan)
        return Response(loan_serializer.data)

