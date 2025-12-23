from django.test import TestCase
from .models import Author, Loan, Book, Member
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .tasks import check_overdue_loans
from django.urls import reverse

User = get_user_model()

class CheckOverdueLoanNotificationTest(TestCase):
    @patch("library.tasks.send_overdue_notification.delay")
    def test_overdue_loan_trigger_notification(self, mock_delay):
        author = Author.objects.create(
            first_name="Dan", last_name="Brown"
        )
        book = Book.objects.create(
            title="Inferno",
            author=author,
            isbn="isbn-1",
            genre='fiction'
        )
        user = User.objects.create_user(
            username="test",
            email="test@mail.com",
            password="test1234"
        )
        member = Member.objects.create(
            user=user
        )

        # overdue loan

        Loan.objects.create(
            book=book,
            member=member,
            due_date=timezone.now().date() - timedelta(days=1)
        )
        # call the tasks
        check_overdue_loans()

        self.assertEqual(mock_delay.call_count, 1)


class BookViewSetTest(TestCase):
    def test_book_list_pagination(self):
        author = Author.objects.create(
            first_name="Dan", last_name="Brown"
        )
        for i in range(20):
            book = Book.objects.create(
                title=f"Inferno {i}",
                author=author,
                isbn=f"isbn-{i}",
                genre='fiction'
            )

        response = self.client.get(reverse('book-list'))

        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data['results']), 10)  # we set page_size 10 in CustomPageNumberPagination

