from celery import shared_task
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass


@shared_task
def send_overdue_notification(username, member_email, book_title):
    send_mail(
        subject='Overdue Loan Reminder',
        message=f'Hello {username},\n\nYou have an overdue book: "{book_title}".\nPlease return it as soon as possible.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member_email],
        fail_silently=False,
    )


@shared_task
def check_overdue_loans():
    try:
        """
            daily tasks to check overdue laons and send notification
        """
        overdue_loans = Loan.objects.select_related('member__user', 'book').filter(
            is_returned=False, due_date__lt=timezone.now().date()
        )
        for loan in overdue_loans:
            if loan.member.user.email:
                send_overdue_notification.delay(
                    username=loan.member.user.username,
                    member_email=loan.member.user.email,
                    book_title=loan.book.title
                )

    except Exception as e:
        print(f"check overdue task failed: {e}")
